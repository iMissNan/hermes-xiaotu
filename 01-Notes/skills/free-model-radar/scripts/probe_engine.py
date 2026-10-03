#!/usr/bin/env python3
"""规约优先 + 两级测试引擎（probe_engine.py）

测试分级与规约优先硬性原则：
1. L1 极轻心跳（日常巡检）：
   - 极小请求（1-2 token，max_tokens=1），只验证基本存活、HTTP状态与首字延迟（首字<3s即极速）。
   - 消耗接近 0，快速大盘巡检。
2. L2 规约核验与五维深测：
   - 规约优先原则：若 vendors.yaml 中某个模型已注明官方参数（如 context_length: 128000），
     L2 仅做最小抽样核准（1发目标长度核验），严禁盲发 32K/131K 探测包；
   - 只有官方未声明参数时，才调用扣基线二分测试探知真实上限；
   - 包含：存活/思考链兼容、延迟、流式吞吐 (tok/s)、限流阈值 (6发数429)。
3. 数据沉淀：
   - 结果自动更新至 models_current 并追加流水至 probe_history。
"""

import json
import os
import sqlite3
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
SMALL_PROMPT = "用一句话解释什么是黑洞。"


def get_current_time_str():
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


def call_chat_api(url, key, model, max_tokens=1000, timeout=120, stream=False, content=SMALL_PROMPT, temperature=0.2):
    """底层调用 10Router /v1/chat/completions"""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    if stream:
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if stream:
                parts = []
                first_s = None
                usage = None
                has_stream_error = False
                stream_err_msg = ""
                total_chunks = 0
                for line in r:
                    s = line.decode(errors="replace").strip()
                    if s.startswith("data: ") and s != "data: [DONE]":
                        total_chunks += 1
                        try:
                            j = json.loads(s[6:])
                            if "error" in j:
                                has_stream_error = True
                                stream_err_msg = str(j["error"])
                            if j.get("usage"):
                                usage = j["usage"]
                            choices = j.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                c_token = delta.get("content") or delta.get("reasoning") or delta.get("reasoning_content")
                                if first_s is None and c_token:
                                    first_s = round(time.time() - t0, 2)
                                if delta.get("content"):
                                    parts.append(delta["content"])
                                elif delta.get("reasoning") or delta.get("reasoning_content"):
                                    parts.append(delta.get("reasoning") or delta.get("reasoning_content"))
                        except Exception:
                            pass
                text = "".join(parts)
                sec = round(time.time() - t0, 2)
                ctok = (usage or {}).get("completion_tokens") or 0
                if has_stream_error and not text and ctok == 0:
                    return {
                        "ok": False,
                        "sec": sec,
                        "first_s": None,
                        "completion_tokens": 0,
                        "prompt_tokens": None,
                        "text": "",
                        "ralen": 0,
                        "http": 429 if "rate limit" in stream_err_msg.lower() or "429" in stream_err_msg else 500,
                        "err": stream_err_msg[:300]
                    }
                return {
                    "ok": True,
                    "sec": sec,
                    "first_s": first_s or sec,
                    "completion_tokens": ctok,
                    "prompt_tokens": (usage or {}).get("prompt_tokens"),
                    "text": text[:60],
                    "ralen": 0,
                    "http": 200,
                    "total_chunks": total_chunks
                }
            else:
                d = json.loads(r.read().decode())
                sec = round(time.time() - t0, 2)
                m0 = (d.get("choices") or [{}])[0].get("message", {}) or {}
                reasoning = m0.get("reasoning_content") or m0.get("reasoning") or ""
                return {
                    "ok": True,
                    "sec": sec,
                    "first_s": None,
                    "completion_tokens": (d.get("usage") or {}).get("completion_tokens"),
                    "prompt_tokens": (d.get("usage") or {}).get("prompt_tokens"),
                    "text": (m0.get("content") or "")[:60],
                    "ralen": len(reasoning),
                    "http": 200
                }
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode(errors="replace")[:300]
        return {
            "ok": False,
            "sec": round(time.time() - t0, 2),
            "http": e.code,
            "err": err_msg
        }
    except Exception as e:
        return {
            "ok": False,
            "sec": round(time.time() - t0, 2),
            "http": 0,
            "err": repr(e)[:300]
        }


def probe_l1_heartbeat(url, key, model, stream_only=False):
    """L1 极轻心跳测试：单发 25 token，极小开销验证存活"""
    stream = True if stream_only else False
    res = call_chat_api(url, key, model, max_tokens=25, timeout=15, stream=stream, content="hi")

    # 思考型与流式存活铁律：正文非空、思考链非空、流式首字非空、返回token>0或拿到有效chunk均算存活
    ctok = res.get("completion_tokens") or 0
    is_alive = res["ok"] and (
        bool(res.get("text")) or
        bool(res.get("ralen")) or
        (stream and res.get("first_s") is not None) or
        ctok > 0 or
        (stream and res.get("total_chunks", 0) > 0)
    )
    latency_ms = int(res["sec"] * 1000)

    return {
        "probe_type": "heartbeat",
        "model": model,
        "alive": is_alive,
        "latency_ms": latency_ms,
        "http_code": res.get("http", 200 if res["ok"] else 0),
        "first_s": res.get("first_s"),
        "error": res.get("err") if not res["ok"] else None
    }


def verify_context_spec_priority(url, key, model, known_specs, stream_only=False):
    """规约优先上下文测试：
    1. 若已声明 context_length，只构造一发接近已声明上限（90%）的核准包，严禁盲发两发；
    2. 若未声明，才进行 32K / 131K 探针；
    """
    spec_ctx = (known_specs or {}).get("context_length")

    # 扣基线发：获取系统注入固定 token 消耗
    r0 = call_chat_api(url, key, model, max_tokens=10, timeout=30, stream=stream_only, content="hello")
    if not r0["ok"] or not r0.get("prompt_tokens"):
        return {"mode": "spec_verify" if spec_ctx else "bisection", "status": "baseline_failed", "error": r0.get("err")}

    baseline = r0["prompt_tokens"]

    # 净内容校准发：1000字
    mid = "量子计算" * 250
    rm = call_chat_api(url, key, model, max_tokens=10, timeout=40, stream=stream_only, content=mid)
    if not rm["ok"] or not rm.get("prompt_tokens") or rm["prompt_tokens"] <= baseline:
        return {"mode": "spec_verify" if spec_ctx else "bisection", "status": "calibration_failed", "error": rm.get("err")}

    chars_per_tok = len(mid) / (rm["prompt_tokens"] - baseline)

    targets = [spec_ctx] if spec_ctx else [32768, 131072]
    target_results = []

    for tgt in targets:
        # 规约验证包：打 tgt 的 85% 保护位，验证是否被上游合法接受
        check_tokens = int(tgt * 0.85)
        chars = max(10, int((check_tokens - baseline) * chars_per_tok))
        pack = "数据" * (chars // 2)

        r = call_chat_api(url, key, model, max_tokens=10, timeout=90, stream=stream_only, content=pack)
        if r["ok"]:
            target_results.append({
                "target_spec": tgt,
                "verified": True,
                "status": "ACCEPTED" if (r.get("prompt_tokens") or 0) >= check_tokens * 0.8 else "ACCEPTED_NOUSAGE",
                "ptok_actual": r.get("prompt_tokens")
            })
        else:
            target_results.append({
                "target_spec": tgt,
                "verified": False,
                "status": "context_length_exceeded" if r.get("http") == 400 else "http_error",
                "http_code": r.get("http"),
                "error": r.get("err")
            })

    return {
        "mode": "spec_verify" if spec_ctx else "bisection",
        "declared_ctx": spec_ctx,
        "results": target_results
    }


def probe_l2_benchmark(url, key, model, known_specs=None, stream_only=False, skip_ratelimit=False):
    """L2 规约校准 + 五维深测引擎"""
    report = {"model": model, "timestamp": get_current_time_str()}

    # 1. 存活与首字延迟
    stream_probe = call_chat_api(url, key, model, max_tokens=500, timeout=45, stream=True, content="写一段百字简述量子纠缠。")
    is_alive = stream_probe["ok"] and (stream_probe.get("text") or (stream_probe.get("first_s") is not None))

    report["alive"] = is_alive
    report["first_token_sec"] = stream_probe.get("first_s")
    report["total_sec"] = stream_probe.get("sec")
    report["http_code"] = stream_probe.get("http", 200 if stream_probe["ok"] else 0)

    if not is_alive:
        report["error"] = stream_probe.get("err")
        report["verdict"] = "deprecated"
        return report

    # 2. 吞吐 (TPS)
    ctok = stream_probe.get("completion_tokens")
    first_s = stream_probe.get("first_s") or 0.1
    sec = stream_probe.get("sec", 1.0)
    if ctok and sec > first_s:
        tps = round(ctok / (sec - first_s), 1)
    else:
        # 若未返回 usage 或时间极短，给一个合理估计或标记
        tps = None
    report["tps"] = tps

    # 3. 上下文能力（严格遵守规约优先原则）
    report["context"] = verify_context_spec_priority(url, key, model, known_specs, stream_only)

    # 4. 限流测定（6 发并发数 429）
    if not skip_ratelimit:
        codes = []
        first_429 = None
        for i in range(6):
            r = call_chat_api(url, key, model, max_tokens=20, timeout=15, stream=stream_only, content="ping")
            code = 200 if r["ok"] else r.get("http", 0)
            codes.append(code)
            if code == 429 and first_429 is None:
                first_429 = i + 1
        report["ratelimit"] = {
            "codes": codes,
            "first_429_shot": first_429,
            "tolerated": 6 if first_429 is None else (first_429 - 1)
        }

    # 5. 综合判语：primary (可当主力) / fallback (只可兜底) / deprecated (弃用)
    ctx_ok = any(t.get("verified", False) for t in report["context"].get("results", []))
    if is_alive and (tps is None or tps >= 30) and ctx_ok and (not report.get("ratelimit") or report["ratelimit"]["tolerated"] >= 4):
        verdict = "primary"
    elif is_alive:
        verdict = "fallback"
    else:
        verdict = "deprecated"

    report["verdict"] = verdict
    return report


def save_probe_result(db_path, model_id, vendor, probe_data, known_specs=None):
    """持久化保存至 sqlite：更新 models_current 并写入 probe_history"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    now_str = get_current_time_str()

    probe_type = probe_data.get("probe_type", "benchmark")
    latency_ms = probe_data.get("latency_ms") or int((probe_data.get("total_sec") or 0) * 1000)
    tps = probe_data.get("tps")
    http_code = probe_data.get("http_code", 200)
    error_raw = probe_data.get("error")

    # 1. 写入历史流水表
    cur.execute('''
        INSERT INTO probe_history (model_id, probe_type, latency_ms, tps, http_code, error_raw, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (model_id, probe_type, latency_ms, tps, http_code, error_raw, json.dumps(probe_data, ensure_ascii=False), now_str))

    # 2. 自动修剪 30 天以前的流水数据
    cur.execute('''
        DELETE FROM probe_history WHERE created_at < datetime('now', '-30 days')
    ''')

    # 3. 状态快照更新
    status = "alive" if probe_data.get("alive") else ("degraded" if http_code in (429, 502, 504) else "dead")
    verdict = probe_data.get("verdict", "unknown")

    measured_specs = {
        "latency_ms": latency_ms,
        "first_token_sec": probe_data.get("first_token_sec"),
        "tps": tps,
        "context_status": probe_data.get("context"),
        "ratelimit": probe_data.get("ratelimit")
    }

    cur.execute('''
        INSERT INTO models_current (model_id, vendor, full_path, official_specs, measured_specs, status, verdict, last_heartbeat, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(model_id) DO UPDATE SET
            vendor=excluded.vendor,
            official_specs=COALESCE(excluded.official_specs, models_current.official_specs),
            measured_specs=excluded.measured_specs,
            status=excluded.status,
            verdict=excluded.verdict,
            last_heartbeat=CASE WHEN excluded.status='alive' THEN excluded.updated_at ELSE models_current.last_heartbeat END,
            updated_at=excluded.updated_at
    ''', (
        model_id,
        vendor,
        model_id,
        json.dumps(known_specs, ensure_ascii=False) if known_specs else None,
        json.dumps(measured_specs, ensure_ascii=False),
        status,
        verdict,
        now_str if status == "alive" else None,
        now_str
    ))

    conn.commit()
    conn.close()
