#!/usr/bin/env python3
"""v3.0 独立双轨前哨发现与 10Router 网关对拍器（crawler.py）

核心原则与架构要求：
1. 彻底剥离网关本地旧账：
   - 严禁从 10Router 本地源码/注册表目录（如 open-sse/...）回退读取模型！
   - 雷达是 100% 独立于网关的前哨侦察兵，直接连接厂商一手源。
2. 外部一手前哨探针架构 (sniff_vendor_shelf)：
   - package_introspect: 直连官方 NPM registry API，提取最新发布版本号、发布时间及生产 tarball 核心模型定义；若遇阻断安全降级至 fallback_doc_url 解析。
   - dynamic_shelf: 直连官方客户端推荐接口（如 Cline），提取 free/promotional 数组，联动 OpenRouter :free 开放免费池。
   - doc_table: 解析官方规约文档与活动站 HTML 表格/列表模型、上下文与 0 Credits 限免信息。
   - openapi: 直连标准 /v1/models 枚举原子模型。
3. 纯净网关硬核差集对拍 (cross_check_gateway)：
   - 仅从 10Router 数据库（kv 表路由别名、providerConnections 表活跃连接与 modelLock）与在线模型表读取当前实际装配；
   - 规范化计算三大差集：
     * dual_matched: 官方最新货架存在且网关已装配生效
     * newly_discovered: 官方一手新出但网关尚未配置（漏配）
     * ghost_mounted: 官方已下架但网关残留挂载（幽灵）
   - 透视底层账号状态（登记账号数、活跃账号数、全未激活警示）。
"""

import datetime
import io
import json
import os
import re
import tarfile
import urllib.request
import urllib.error
import yaml

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config/vendors.yaml")
LOCAL_PROXY_URL = "http://127.0.0.1:7892"

# 针对 Qoder 等使用缩写别名模型的映射字典（辅助规范化比对）
QODER_MODEL_ALIASES = {
    "qfmodel": "qwen3.8-flash",
    "qmodel_38max": "qwen3.8-max",
    "q37fmodel": "qwen3.7-flash",
    "dfmodel": "deepseek-v4-flash",
    "dmodel": "deepseek-v4-pro",
    "gfmodel": "glm-5.3-flash",
    "gmodel": "glm-5.2",
    "gm51model": "glm-5.1",
    "kmodel": "kimi-k2.7-code",
    "kmodel_latest": "kimi-k3",
    "mmodel": "minimax-m2.7",
}


def load_config(config_path=DEFAULT_CONFIG_PATH):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_router_key(router_db_path):
    import sqlite3
    db = sqlite3.connect(f"file:{router_db_path}?mode=ro", uri=True)
    row = db.execute("SELECT key FROM apiKeys WHERE isActive=1 LIMIT 1").fetchone()
    db.close()
    if not row:
        raise RuntimeError("No active apiKey found in 10Router db")
    return row[0]


def fetch_gateway_models(gateway_url, api_key):
    """从 10Router 获取当前在线的所有模型列表"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        f"{gateway_url.rstrip('/')}/v1/models",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    with opener.open(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    return [m["id"] for m in data.get("data", [])]


def fetch_url_content(url, proxy_url=LOCAL_PROXY_URL, timeout=8, headers=None):
    """通用 URL 抓取助手：支持代理请求并在失败时尝试直连回退"""
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if headers:
        hdrs.update(headers)

    attempts = []
    if proxy_url:
        attempts.append(("proxy", proxy_url))
    attempts.append(("direct", None))

    last_err = None
    for mode, pxy in attempts:
        try:
            proxies = {"http": pxy, "https": pxy} if pxy else {}
            opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
            req = urllib.request.Request(url, headers=hdrs)
            with opener.open(req, timeout=timeout) as resp:
                data = resp.read()
                return {
                    "ok": True,
                    "mode": mode,
                    "status": resp.status,
                    "data": data,
                    "text": data.decode("utf-8", errors="replace")
                }
        except Exception as e:
            last_err = e

    return {"ok": False, "error": str(last_err)}


def format_publish_time(raw_time):
    """规范化时间戳为北京时间 (UTC+8) 可读字符串"""
    if not raw_time:
        return "未知"
    try:
        if isinstance(raw_time, (int, float)):
            sec = raw_time / 1000.0 if raw_time > 1e11 else raw_time
            dt = datetime.datetime.fromtimestamp(sec, tz=datetime.timezone(datetime.timedelta(hours=8)))
            return dt.strftime("%Y-%m-%d %H:%M")
        elif isinstance(raw_time, str):
            return raw_time[:16].replace("T", " ")
    except Exception:
        pass
    return str(raw_time)


def parse_html_models_and_specs(html_text):
    """高效解析 HTML 文档中的原子模型名称、上下文规格与促销信息"""
    models = set()
    model_patterns = [
        r'\b(Qwen[0-9\.\-_a-zA-Z]*)\b',
        r'\b(DeepSeek[0-9\.\-_a-zA-Z]*)\b',
        r'\b(GLM[0-9\.\-_a-zA-Z]*)\b',
        r'\b(Kimi[0-9\.\-_a-zA-Z]*)\b',
        r'\b(MiniMax[0-9\.\-_a-zA-Z]*)\b',
        r'\b(qmodel[0-9\.\-_a-zA-Z]*)\b',
        r'\b(qfmodel[0-9\.\-_a-zA-Z]*)\b',
        r'\b(hy4[0-9\.\-_a-zA-Z]*)\b',
    ]

    contexts = []
    table_matches = re.findall(r'<table[^>]*>(.*?)</table>', html_text, re.DOTALL | re.I)
    for t in table_matches:
        for r in re.findall(r'<tr[^>]*>(.*?)</tr>', t, re.DOTALL | re.I):
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.DOTALL | re.I)
            cleaned_cells = [' '.join(re.sub(r'<[^>]+>', ' ', c).split()) for c in cells]
            if cleaned_cells and cleaned_cells[0] not in ('模型名称', '选项', '级别', '模型分级'):
                cand = cleaned_cells[0]
                if any(cand.lower().startswith(p) for p in ('qwen', 'deepseek', 'glm', 'kimi', 'minimax', 'qmodel', 'qfmodel', 'hy4')):
                    models.add(cand)
            for c in cleaned_cells:
                for ctx_m in re.findall(r'\b\d+[KkMmBb]\b', c):
                    if ctx_m not in contexts:
                        contexts.append(ctx_m)

    if len(models) < 3:
        for pat in model_patterns:
            for m in re.findall(pat, html_text, re.I):
                m_lower = m.lower()
                if len(m) > 2 and not m_lower.endswith(('-discount', '-offer', '-glasses', '-guide', '-api', '-series', '-key')):
                    models.add(m)

    promos = []
    for h in re.findall(r'<h[1-4][^>]*>(.*?)</h[1-4]>', html_text, re.DOTALL | re.I):
        clean = ' '.join(re.sub(r'<[^>]+>', ' ', h).split()).replace('\u200b', '').strip()
        if clean and len(clean) > 3 and clean != 'Documentation Index':
            if any(k in clean for k in ['免费', '活动', '折扣', 'Credits', '优惠']):
                if clean not in promos:
                    promos.append(clean)

    for p in re.findall(r'<p[^>]*>(.*?)</p>', html_text, re.DOTALL | re.I):
        clean = ' '.join(re.sub(r'<[^>]+>', ' ', p).split()).replace('\u200b', '').strip()
        if any(k in clean for k in ['限免', '0.0×', '不消耗 Credits', '免费使用', '0 credits', '0 Credits']):
            if 15 < len(clean) < 120 and clean not in promos:
                promos.append(clean)
        if len(promos) >= 5:
            break

    return sorted(list(models)), sorted(contexts)[:6], promos[:5]


def sniff_package_introspect(pkg_name, registry_url, fallback_doc_url=None, timeout=8):
    """策略 1 (package_introspect): 一手 NPM 官方生产发版自省引擎
    - 直连官方 NPM registry API，抓取最新发布版本 (version)、发布时间 (publish_time) 与 tarball 地址；
    - 流式解包或精准解析发版包内模型定义 (product.json / product.internal.json / models.json)；
    - 智能提取真实原子模型清单、零倍率/免额模型、标称上下文窗口；
    - 若遇网络或包内特殊阻断，平滑安全降级至 fallback_doc_url 解析，绝不崩溃；
    - 返回携带 source: package_introspect、version、publish_time 等一手证据。
    """
    errors = []
    version = "unknown"
    publish_time_str = "未知"
    tarball_url = None
    extracted_models = []
    zero_credit_models = []
    context_hints = []
    events_summary = []

    # 1. 查询 NPM Registry 元数据
    try:
        req = urllib.request.Request(registry_url, headers={"User-Agent": "free-model-radar/3.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        version = data.get("version", "unknown")
        raw_time = data.get("publish_time") or (data.get("time", {}).get(version))
        publish_time_str = format_publish_time(raw_time)
        tarball_url = data.get("dist", {}).get("tarball")
    except Exception as e:
        errors.append(f"npm_registry_error: {e}")

    # 2. 从官方发版 tarball 流式提取模型定义
    if tarball_url:
        try:
            req_tb = urllib.request.Request(tarball_url, headers={"User-Agent": "free-model-radar/3.0"})
            with urllib.request.urlopen(req_tb, timeout=timeout) as resp_tb:
                tf = tarfile.open(fileobj=resp_tb, mode="r|*")
                for member in tf:
                    if member.name.endswith(("product.json", "product.internal.json", "models.json")):
                        f = tf.extractfile(member)
                        if f:
                            try:
                                d = json.loads(f.read().decode("utf-8", errors="ignore"))
                                m_list = d.get("models", [])
                                if isinstance(m_list, list):
                                    for item in m_list:
                                        if isinstance(item, dict):
                                            mid = item.get("id")
                                            # 过滤纯逻辑分组抽象名称
                                            if mid and not mid.endswith("-model") and mid not in ("default", "craft"):
                                                if mid not in extracted_models:
                                                    extracted_models.append(mid)
                                                c = str(item.get("credits", "")).lower()
                                                if "x0.00" in c or "0.0x" in c or "free" in c or c == "":
                                                    if mid not in zero_credit_models:
                                                        zero_credit_models.append(mid)
                                                ctx = item.get("maxAllowedSize") or item.get("maxInputTokens")
                                                if ctx:
                                                    ctx_str = f"{int(ctx // 1000000)}M" if ctx >= 1000000 else f"{int(ctx // 1000)}K"
                                                    if ctx_str not in context_hints:
                                                        context_hints.append(ctx_str)
                                elif isinstance(m_list, dict):
                                    for mid, item in m_list.items():
                                        if mid not in extracted_models:
                                            extracted_models.append(mid)
                            except Exception as ex:
                                errors.append(f"parse_json_err: {ex}")
                        if len(extracted_models) >= 15:
                            break
        except Exception as e:
            errors.append(f"tarball_err: {e}")

    # 3. 伴生与国际服多端核心对齐处理（WorkBuddy 国际服与国服同源同构内核）
    if not extracted_models and "workbuddy" in pkg_name:
        try:
            companion_url = "https://registry.npmmirror.com/@tencent-ai/codebuddy-code/latest"
            req_comp = urllib.request.Request(companion_url, headers={"User-Agent": "free-model-radar/3.0"})
            with urllib.request.urlopen(req_comp, timeout=timeout) as resp_comp:
                data_comp = json.loads(resp_comp.read().decode("utf-8"))
            comp_ver = data_comp.get("version", "")
            comp_tb = data_comp.get("dist", {}).get("tarball")
            if comp_tb:
                req_tb = urllib.request.Request(comp_tb, headers={"User-Agent": "free-model-radar/3.0"})
                with urllib.request.urlopen(req_tb, timeout=timeout) as resp_tb:
                    tf = tarfile.open(fileobj=resp_tb, mode="r|*")
                    for member in tf:
                        if member.name.endswith("product.json"):
                            f = tf.extractfile(member)
                            if f:
                                d = json.loads(f.read().decode("utf-8", errors="ignore"))
                                for item in d.get("models", []):
                                    if isinstance(item, dict):
                                        mid = item.get("id")
                                        if mid and not mid.endswith("-model") and mid not in ("default", "craft"):
                                            if mid not in extracted_models:
                                                extracted_models.append(mid)
                                            c = str(item.get("credits", "")).lower()
                                            if "x0.00" in c or "0.0x" in c or "free" in c or c == "":
                                                if mid not in zero_credit_models:
                                                    zero_credit_models.append(mid)
                                            ctx = item.get("maxAllowedSize") or item.get("maxInputTokens")
                                            if ctx:
                                                ctx_str = f"{int(ctx // 1000000)}M" if ctx >= 1000000 else f"{int(ctx // 1000)}K"
                                                if ctx_str not in context_hints:
                                                    context_hints.append(ctx_str)
                            break
            if extracted_models:
                events_summary.append(f"官方多端内核对齐 (CodeBuddy Core Engine v{comp_ver})")
        except Exception as ex:
            errors.append(f"companion_error: {ex}")

    # 4. 回退解析 fallback_doc_url
    if not extracted_models and fallback_doc_url:
        try:
            req_doc = urllib.request.Request(fallback_doc_url, headers={"User-Agent": "free-model-radar/3.0"})
            with urllib.request.urlopen(req_doc, timeout=timeout) as resp_doc:
                html = resp_doc.read().decode("utf-8", errors="replace")
                m_list, ctx_h, promos = parse_html_models_and_specs(html)
                for m in m_list:
                    if m not in extracted_models:
                        extracted_models.append(m)
                for c in ctx_h:
                    if c not in context_hints:
                        context_hints.append(c)
                events_summary.extend(promos)
        except Exception as ex:
            errors.append(f"fallback_doc_error: {ex}")

    if zero_credit_models:
        events_summary.append(f"零倍率/完全免额模型: {', '.join(zero_credit_models[:4])}")

    context_hints = sorted(list(set(context_hints)))
    return {
        "ok": bool(extracted_models) or (version != "unknown"),
        "source": "package_introspect",
        "package_name": pkg_name,
        "version": version,
        "publish_time": publish_time_str,
        "tarball_url": tarball_url,
        "free_models": extracted_models,
        "zero_credit_models": zero_credit_models,
        "context_hints": context_hints,
        "events_summary": events_summary,
        "errors": errors
    }


def sniff_vendor_shelf(vendor_info, proxy_url=LOCAL_PROXY_URL, timeout=8):
    """前哨独立发现引擎：通用元数据驱动嗅探
    
    支持策略：
    - package_introspect: 官方 NPM registry 生产发版自省（WorkBuddy 等）；
    - dynamic_shelf: API 请求，提取 free、promotional 数组，联动 openrouter_free（Cline 等）；
    - doc_table: 请求文档 URL 及 events_url，解析 HTML 表格/列表模型、上下文与 0 Credits 限免信息（Qoder 等）；
    - openapi: 请求 /v1/models 枚举模型（NVIDIA NIM、AMD 等）；
    - 其它 / 回退: 调用 sniffer_official_doc。
    """
    vendor_id = vendor_info.get("vendor_id") if isinstance(vendor_info, dict) else str(vendor_info)
    ret = {
        "vendor_id": vendor_id,
        "discovery_type": "unknown",
        "ok": False,
        "free_models": [],
        "openrouter_free": [],
        "promotional_models": [],
        "context_hints": [],
        "events_summary": [],
        "version": None,
        "publish_time": None,
        "raw_shelf": {},
        "errors": []
    }

    if not isinstance(vendor_info, dict):
        ret["errors"].append("vendor_info is not dict")
        return ret

    discovery = vendor_info.get("discovery") or {}
    disc_type = discovery.get("type", "")
    ret["discovery_type"] = disc_type or "fallback_doc"

    # ---------------- 策略 1: package_introspect ----------------
    if disc_type == "package_introspect":
        pkg_name = discovery.get("package_name") or vendor_info.get("package_name")
        registry_url = discovery.get("registry_url") or f"https://registry.npmmirror.com/{pkg_name}/latest"
        fallback_doc = discovery.get("fallback_doc_url") or vendor_info.get("doc_url")
        pkg_res = sniff_package_introspect(pkg_name, registry_url, fallback_doc_url=fallback_doc, timeout=timeout)
        ret["ok"] = pkg_res.get("ok", False)
        ret["free_models"] = pkg_res.get("free_models", [])
        ret["context_hints"] = pkg_res.get("context_hints", [])
        ret["events_summary"] = pkg_res.get("events_summary", [])
        ret["version"] = pkg_res.get("version")
        ret["publish_time"] = pkg_res.get("publish_time")
        ret["errors"].extend(pkg_res.get("errors", []))

    # ---------------- 策略 2: dynamic_shelf ----------------
    elif disc_type == "dynamic_shelf":
        disc_url = discovery.get("url") or vendor_info.get("doc_url")
        res = fetch_url_content(disc_url, proxy_url=proxy_url, timeout=timeout, headers={"User-Agent": "Cline/3.0.0 (compatible; FreeModelRadar/3.0)"})
        if res.get("ok"):
            try:
                data = json.loads(res["text"])
                ret["ok"] = True
                ret["raw_shelf"] = data
                for item in data.get("free", []):
                    m_id = item.get("id") if isinstance(item, dict) else str(item)
                    if m_id and m_id not in ret["free_models"]:
                        ret["free_models"].append(m_id)

                for item in data.get("clinePass", []):
                    m_id = item.get("id") if isinstance(item, dict) else str(item)
                    if m_id and m_id not in ret["promotional_models"]:
                        ret["promotional_models"].append(m_id)

                for item in data.get("recommended", []):
                    m_id = item.get("id") if isinstance(item, dict) else str(item)
                    if m_id and m_id not in ret["promotional_models"]:
                        ret["promotional_models"].append(m_id)
            except Exception as e:
                ret["errors"].append(f"dynamic_shelf_json_error: {e}")
        else:
            ret["errors"].append(f"dynamic_shelf_fetch_error: {res.get('error')}")

        if discovery.get("openrouter_free"):
            or_url = "https://openrouter.ai/api/v1/models"
            or_res = fetch_url_content(or_url, proxy_url=proxy_url, timeout=timeout)
            if or_res.get("ok"):
                try:
                    or_data = json.loads(or_res["text"])
                    for item in or_data.get("data", []):
                        m_id = item.get("id", "")
                        if m_id.endswith(":free") and m_id not in ret["openrouter_free"]:
                            ret["openrouter_free"].append(m_id)
                except Exception as e:
                    ret["errors"].append(f"openrouter_parse_error: {e}")
            else:
                ret["errors"].append(f"openrouter_fetch_error: {or_res.get('error')}")

    # ---------------- 策略 3: doc_table ----------------
    elif disc_type == "doc_table":
        disc_url = discovery.get("url") or vendor_info.get("doc_url")
        res = fetch_url_content(disc_url, proxy_url=proxy_url, timeout=timeout)
        if res.get("ok"):
            ret["ok"] = True
            m_list, ctx_hints, promos = parse_html_models_and_specs(res["text"])
            ret["free_models"] = m_list
            ret["context_hints"] = ctx_hints
            ret["events_summary"].extend(promos)
        else:
            ret["errors"].append(f"doc_table_fetch_error: {res.get('error')}")

        events_url = discovery.get("events_url") or vendor_info.get("events_url")
        if events_url and events_url != disc_url:
            ev_res = fetch_url_content(events_url, proxy_url=proxy_url, timeout=timeout)
            if ev_res.get("ok"):
                _, _, ev_promos = parse_html_models_and_specs(ev_res["text"])
                for ep in ev_promos:
                    if ep not in ret["events_summary"]:
                        ret["events_summary"].append(ep)
            else:
                ret["errors"].append(f"events_fetch_error: {ev_res.get('error')}")

    # ---------------- 策略 4: openapi ----------------
    elif disc_type == "openapi":
        disc_url = discovery.get("url") or vendor_info.get("api_endpoint")
        res = fetch_url_content(disc_url, proxy_url=proxy_url, timeout=timeout)
        if res.get("ok"):
            try:
                data = json.loads(res["text"])
                ret["ok"] = True
                ret["raw_shelf"] = data
                models = []
                for item in data.get("data", []):
                    m_id = item.get("id", "")
                    if m_id:
                        models.append(m_id)
                ret["free_models"] = models
            except Exception as e:
                ret["errors"].append(f"openapi_json_error: {e}")
        else:
            ret["errors"].append(f"openapi_fetch_error: {res.get('error')}")

    # ---------------- 策略 5: 回退到通用网页嗅探 ----------------
    else:
        fallback_url = vendor_info.get("doc_url") or vendor_info.get("events_url")
        doc_res = sniffer_official_doc(fallback_url, timeout=timeout)
        if doc_res.get("ok"):
            ret["ok"] = True
            ret["context_hints"] = doc_res.get("context_hints", [])
            ret["events_summary"] = doc_res.get("pricing_hints", [])
        else:
            ret["errors"].append(f"fallback_sniff_error: {doc_res.get('error') or doc_res.get('reason')}")

    return ret


def sniff_client_shelf(vendor_id="cline", proxy_url=LOCAL_PROXY_URL, timeout=8):
    """向后兼容包装层"""
    cfg = load_config()
    vendors = cfg.get("vendors", {})
    v_info = vendors.get(vendor_id)
    if not v_info:
        v_info = {
            "vendor_id": vendor_id,
            "discovery": {
                "type": "dynamic_shelf" if vendor_id == "cline" else "doc_table",
                "url": "https://api.cline.bot/api/v1/ai/cline/recommended-models" if vendor_id == "cline" else "",
                "openrouter_free": (vendor_id == "cline")
            }
        }
    return sniff_vendor_shelf(v_info, proxy_url=proxy_url, timeout=timeout)


def cross_check_gateway(vendor_id, external_free_models, router_db_path, gateway_binding=None):
    """10Router 现网纯净硬核差集对拍：
    - 读取 gateway_binding 中的 alias_prefixes 扫描 kv 表活跃映射；
    - 读取 gateway_binding 中的 provider_names 扫描 providerConnections 表（已挂载模型与底层账号状态）；
    - 结合 /v1/models 在线接口获取网关真实装配暴露清单；
    - 规范化比对，精确计算 dual_matched、newly_discovered、ghost_mounted；
    - 汇总底层账号状态（总数、活跃数、全未激活预警）。
    """
    import sqlite3

    if not os.path.exists(router_db_path):
        return {"error": f"router db not found: {router_db_path}"}

    if not gateway_binding:
        cfg = load_config()
        v_info = cfg.get("vendors", {}).get(vendor_id, {})
        gateway_binding = v_info.get("gateway_binding", {})

    alias_prefixes = gateway_binding.get("alias_prefixes", [vendor_id])
    provider_names = gateway_binding.get("provider_names", [vendor_id])

    db = sqlite3.connect(f"file:{router_db_path}?mode=ro", uri=True)

    # 1. 穿透 10Router 网关 /v1/models 获取权威在线暴露模型
    api_models = []
    try:
        api_key = get_router_key(router_db_path)
        gateway_url = "http://127.0.0.1:20128"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(
            f"{gateway_url.rstrip('/')}/v1/models",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        with opener.open(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            api_models = [m["id"] for m in data.get("data", [])]
    except Exception:
        pass

    # 2. 查询 kv 表中的路由映射
    kv_models = set()
    for pfx in alias_prefixes:
        for r in db.execute("SELECT key, value FROM kv WHERE key LIKE ? OR key = ?", (f"{pfx}|%", pfx)).fetchall():
            try:
                val = json.loads(r[1])
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, str):
                            kv_models.add(item)
                elif isinstance(val, dict):
                    mid = val.get("id", val.get("name", ""))
                    if mid:
                        kv_models.add(mid)
            except Exception:
                pass

    # 3. 查询 providerConnections 表中属于该供应商连接的已挂载模型与账号状态
    conn_models = set()
    accounts = []
    for pname in provider_names:
        for r in db.execute("SELECT id, name, email, isActive, data FROM providerConnections WHERE provider = ?", (pname,)).fetchall():
            d = json.loads(r[4]) if r[4] else {}
            has_tok = bool(d.get("accessToken") or d.get("apiKey") or d.get("token"))
            acc_name = r[1] or r[2] or r[0]
            accounts.append({
                "id": r[0],
                "name": acc_name,
                "email": r[2],
                "isActive": bool(r[3]),
                "has_token": has_tok
            })
            for k in d.keys():
                if k.startswith("modelLock_"):
                    conn_models.add(k[len("modelLock_"):])

    db.close()

    # 4. 从 10Router 在线模型中提取属于该供应商的前缀模型
    matched_api_models = set()
    for m in api_models:
        for pfix in alias_prefixes:
            if m.startswith(f"{pfix}/"):
                matched_api_models.add(m)
            elif m == pfix:
                matched_api_models.add(m)

    gateway_all = kv_models.union(conn_models).union(matched_api_models)
    ext_set = set(external_free_models or [])

    strip_prefixes = list(alias_prefixes) + [vendor_id]

    def simplify(s):
        return re.sub(r'[^a-z0-9]', '', str(s).lower())

    # 构建外部模型的规范化表
    norm_ext = {}
    for m in ext_set:
        m_str = str(m).strip()
        if "/" in m_str:
            pfx, rest = m_str.split("/", 1)
            if pfx.lower() in [p.lower() for p in strip_prefixes]:
                m_str = rest
        norm_ext[simplify(m_str)] = m

    # 构建网关模型的规范化表
    norm_gw = {}
    for m in gateway_all:
        m_str = str(m).strip()
        if "/" in m_str:
            pfx, rest = m_str.split("/", 1)
            if pfx.lower() in [p.lower() for p in strip_prefixes]:
                m_str = rest
        simp = simplify(m_str)
        norm_gw[simp] = m
        # 如果存在 Qoder 别名缩写，双向登记规范化映射
        if m_str in QODER_MODEL_ALIASES:
            full_target = simplify(QODER_MODEL_ALIASES[m_str])
            if full_target not in norm_gw:
                norm_gw[full_target] = m

    # 1. dual_matched: 官方当期存在且网关已装配
    dual_matched_simps = set(norm_ext.keys()).intersection(set(norm_gw.keys()))
    dual_matched = sorted([norm_gw[k] for k in dual_matched_simps])

    # 2. newly_discovered: 官方新出但网关尚未配置
    newly_discovered_simps = set(norm_ext.keys()) - set(norm_gw.keys())
    newly_discovered = sorted([norm_ext[k] for k in newly_discovered_simps])

    # 3. ghost_mounted: 官方已下架但网关残留挂载
    ghost_mounted = []
    if ext_set:
        for k, orig in norm_gw.items():
            if k not in norm_ext:
                # 过滤通用逻辑别名（auto, ultimate, lite 等）
                if any(tag in k for tag in ["free", "stealth", ":free", "v4", "v3", "glm", "qwen", "hy", "kimi", "mini"]):
                    if orig not in ghost_mounted:
                        ghost_mounted.append(orig)
    ghost_mounted = sorted(ghost_mounted)

    total_accounts = len(accounts)
    active_accounts = sum(1 for a in accounts if a["isActive"])
    warning_no_active = (total_accounts > 0 and active_accounts == 0)

    return {
        "vendor_id": vendor_id,
        "dual_matched": dual_matched,
        "newly_discovered": newly_discovered,
        "ghost_mounted": ghost_mounted,
        "gateway_models": sorted(list(gateway_all)),
        "gateway_total_count": len(gateway_all),
        "external_total_count": len(ext_set),
        "accounts": accounts,
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "warning_no_active": warning_no_active
    }


def sniffer_api_models(config=None):
    """网关模型巡检"""
    if config is None:
        config = load_config()

    defaults = config.get("defaults", {})
    gateway_url = defaults.get("gateway_url", "http://127.0.0.1:20128")
    router_db = defaults.get("router_db", "/home/linxuan/.10router-bare-data/db/data.sqlite")

    api_key = get_router_key(router_db)
    all_models = fetch_gateway_models(gateway_url, api_key)

    results = {}
    vendors = config.get("vendors", {})

    for v_key, v_info in vendors.items():
        v_models = v_info.get("models", {})
        registered_set = set(v_models.keys())

        matched_in_gateway = set()
        for m in all_models:
            m_lower = m.lower()
            if v_key in m_lower or (v_key == "qoder-cn" and "qdc" in m_lower):
                matched_in_gateway.add(m)

        active_registered = list(registered_set.intersection(matched_in_gateway))
        missing_in_gateway = list(registered_set - matched_in_gateway)
        discovered_in_gateway = list(matched_in_gateway - registered_set)

        results[v_key] = {
            "vendor_name": v_info.get("name", v_key),
            "registered_count": len(registered_set),
            "active_registered": active_registered,
            "missing_in_gateway": missing_in_gateway,
            "discovered_in_gateway": discovered_in_gateway
        }

    return results


def sniffer_official_doc(url, timeout=8):
    """轻量嗅探官方页面，提取规约线索"""
    if not url:
        return {"ok": False, "reason": "empty_url"}
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FreeModelRadar/3.0)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "error": str(e)[:150]}

    tokens_match = re.findall(r"(\d+[\s\-]?[kKmMbB]?\s*(?:context|tokens?|window))", content, re.I)
    pricing_match = re.findall(r"(free[\s\-]tier|free[\s\-]of[\s\-]charge|promotion|0\s*credits?)", content, re.I)

    return {
        "ok": True,
        "length": len(content),
        "context_hints": list(set(tokens_match))[:5],
        "pricing_hints": list(set(pricing_match))[:5]
    }


if __name__ == "__main__":
    print("=== free-model-radar v3.0 独立双轨前哨自检 ===")
    cfg = load_config()
    for vid in ["workbuddy-cn", "workbuddy", "qoder-cn", "qoder", "cline"]:
        vinfo = cfg.get("vendors", {}).get(vid, {})
        sniff = sniff_vendor_shelf(vinfo)
        print(f"\n[{vid}] 策略: {sniff['discovery_type']}, 成功: {sniff['ok']}")
        if sniff.get("version"):
            print(f"  版本: {sniff['version']} ({sniff.get('publish_time')})")
        print(f"  前哨提取模型: {sniff['free_models'][:6]} (共 {len(sniff['free_models'])} 个)")
        if sniff.get("events_summary"):
            print(f"  限免/活动: {sniff['events_summary'][:2]}")
        cc = cross_check_gateway(vid, sniff["free_models"], cfg["defaults"]["router_db"], vinfo.get("gateway_binding"))
        print(f"  对拍差集: 双向对齐={len(cc['dual_matched'])}, 新发现漏配={len(cc['newly_discovered'])}, 幽灵挂载={len(cc['ghost_mounted'])}")
        print(f"  账号状态: 登记={cc['total_accounts']}, 活跃={cc['active_accounts']}, 全未激活预警={cc['warning_no_active']}")
