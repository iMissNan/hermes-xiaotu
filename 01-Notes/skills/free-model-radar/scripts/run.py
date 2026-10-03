#!/usr/bin/env python3
"""free-model-radar 主控制脚本（run.py）

命令行使用方式：
1. 查询模式 (query)：
   python3 run.py --mode query [--vendor cline] [--model qoder]
2. 巡检模式 (heartbeat)：
   python3 run.py --mode heartbeat [--vendor cline] [--model qoder]
3. 深测模式 (benchmark，规约优先)：
   python3 run.py --mode benchmark --model cline/z-ai/glm-5.3-flash
4. 嗅探模式 (crawl)：
   python3 run.py --mode crawl
5. 建议与卡片模式 (advise)：
   python3 run.py --mode advise --combo yangmao
6. 采纳/换血模式 (apply)：
   python3 run.py --mode apply [--combo yangmao] [--dry-run]
7. 添加供应商 (add-vendor)：
   python3 run.py --mode add-vendor --vendor siliconflow --doc-url https://siliconflow.cn --models m1,m2
8. 移除/禁用供应商 (remove-vendor)：
   python3 run.py --mode remove-vendor --vendor siliconflow
"""

import argparse
import json
import os
import sys
import yaml

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from crawler import (
    load_config,
    get_router_key,
    sniffer_api_models,
    sniffer_official_doc,
    sniff_vendor_shelf,
    sniff_client_shelf,
    cross_check_gateway
)
from probe_engine import (
    probe_l1_heartbeat,
    probe_l2_benchmark,
    save_probe_result
)
from router_advisor import generate_combo_diff, apply_combo_ranking, get_radar_models_status
from feishu_notifier import format_feishu_approval_card


def get_config_path(custom_path=None):
    if custom_path:
        return custom_path
    return os.path.join(SCRIPTS_DIR, "../config/vendors.yaml")


def format_latency(latency_ms, first_token_sec=None):
    """格式化首字延时展示"""
    if first_token_sec is not None and first_token_sec > 0:
        return f"**{first_token_sec}s**"
    if latency_ms is not None and latency_ms > 0:
        sec = round(latency_ms / 1000.0, 1)
        return f"**{sec}s**" if sec < 10 else f"{sec}s"
    return "-"


def format_context_spec(specs):
    """格式化上下文展示，如 64k, 128k"""
    if not specs:
        return "未声明"
    ctx = specs.get("context_length")
    if not ctx:
        return "未知"
    if isinstance(ctx, (int, float)):
        if ctx >= 1000:
            k = int(round(ctx / 1000.0))
            # 常见规格对齐 (128000 -> 128k, 65536 -> 64k, 131072 -> 128k)
            if ctx == 65536:
                return "64k"
            elif ctx in (128000, 131072):
                return "128k"
            return f"{k}k"
        return str(ctx)
    try:
        raw_str = str(ctx).lower().strip()
        if "k" in raw_str:
            return raw_str
        val = int(raw_str)
        if val == 65536:
            return "64k"
        elif val in (128000, 131072):
            return "128k"
        if val >= 1000:
            return f"{int(round(val / 1000.0))}k"
        return str(val)
    except Exception:
        return str(ctx)


def format_verdict_tag(verdict):
    """格式化模型定位/判语"""
    if verdict == "primary":
        return "⭐ 主力"
    elif verdict == "fallback":
        return "🔹 备用"
    elif verdict == "unknown" or not verdict:
        return "⚪ 候选"
    return verdict


def do_help(config=None):
    """输出 fm 指令与帮助全量菜单原生 Markdown 表格"""
    print("### 🧭 free-model-radar（fm）全量指令速查菜单\n")
    print("| 指令分类 | 推荐口令 / 别名 | 真实命令示例 | 功能与行为说明 |")
    print("| :--- | :--- | :--- | :--- |")
    print("| 📊 **查大盘** | `fm全部`、`fm活跃`、`fm active` | `fm全部` | 供应商分块大盘，剔除全失效供应商，展示各家存活模型与定位 |")
    print("| 🏆 **查榜单** | `fm榜单`、`fm top`、`fm排行` | `fm榜单`、`fm top 3` | 存活/主力/低延迟/高吞吐综合测速 Top 推荐榜单 |")
    print("| 🔍 **查单家** | `fm查`、`fm list`、`fm status` | `fm查`、`fm查 qoder`、`fm查 cline` | 查询指定供应商或模型的运行快照、已知规约与状态 |")
    print("| ⚡ **即时测** | `fm测`、`fm test`、`fm benchmark` | `fm测`、`fm测 cline`、`fm测 qoder` | 即时发起 L1 极轻心跳巡检；加具体模型 ID 发起 L2 规约深测 |")
    print("| 🔄 **一键换** | `fm换`、`fm采纳`、`fm apply` | `fm换`、`fm换 yangmao` | 将实测优质模型重排同步至 10Router 网关（自动备份快照防呆） |")
    print("| ➕ **加配置** | `fm加`、`fm添加`、`fm add` | `fm加 siliconflow -m m1,m2` | 快捷向花名册登记新供应商与已知规格 |")
    print("| ⛔ **停监控** | `fm停`、`fm删`、`fm remove` | `fm停 nvidia` | 从花名册移除失效或下架的供应商 |")
    print("| ❓ **查指令** | `fm指令`、`fm帮助`、`fm help` | `fm指令`、`fm help` | 随时调出本功能速查菜单，防止遗忘口令 |")
    print()
    print("💡 **使用提示**：终端支持 `python3 scripts/cli_handler.py \"<口令>\"`，也可在聊天中直接输入口令。")
    return True


def do_active(config):
    """查询今日有效供应商与存活模型大盘（方案二：按供应商分块原生Markdown表格）"""
    from datetime import datetime, timezone, timedelta
    tz_bj = timezone(timedelta(hours=8))
    today_bj = datetime.now(tz_bj).strftime("%Y-%m-%d")

    defaults = config.get("defaults", {})
    radar_db = defaults.get("sqlite_db", "/home/linxuan/.hermes/data/model-radar.sqlite")
    status_map = get_radar_models_status(radar_db)
    vendors = config.get("vendors", {})

    valid_vendors = []
    filtered_vendors = []

    total_alive_models = 0
    total_primary_models = 0

    for v_key, v_info in vendors.items():
        v_models = v_info.get("models", {})
        alive_models = []
        dead_or_unregistered = []

        for m_id, m_info in v_models.items():
            st = status_map.get(m_id)
            if not st:
                dead_or_unregistered.append((m_id, "未入库"))
                continue
            if st.get("status") == "alive":
                alive_models.append((m_id, m_info, st))
                total_alive_models += 1
                if st.get("verdict") == "primary":
                    total_primary_models += 1
            else:
                dead_or_unregistered.append((m_id, "已失效/dead"))

        if alive_models:
            valid_vendors.append({
                "vendor_id": v_key,
                "name": v_info.get("name", v_key),
                "doc_url": v_info.get("doc_url", "N/A"),
                "stream_only": v_info.get("stream_only", False),
                "alive_models": alive_models,
                "total_count": len(v_models)
            })
        else:
            reason = "全线下架/超时" if dead_or_unregistered else "未登记模型"
            filtered_vendors.append({
                "vendor_id": v_key,
                "name": v_info.get("name", v_key),
                "reason": reason
            })

    print(f"### 📊 今日可用算力大盘概览（{today_bj}）\n")
    print(f"- **有效供应商**: {len(valid_vendors)} 家 | **存活模型**: {total_alive_models} 个 | **主力推荐**: {total_primary_models} 个\n")

    if not valid_vendors:
        print("> ⚠️ **警告**：当前暂无任何处于 `alive` 存活状态的有效供应商！请先运行 `fm测` 触发巡检。\n")
    else:
        for v in valid_vendors:
            doc_link = f"[{v['doc_url']}]({v['doc_url']})" if v['doc_url'].startswith("http") else v['doc_url']
            alive_cnt = len(v['alive_models'])
            tot_cnt = v['total_count']
            stream_note = " · 仅流式" if v['stream_only'] else ""
            print(f"##### 🏢 {v['name']} (存活 {alive_cnt}/{tot_cnt}{stream_note} · 文档: {doc_link})\n")
            print("| 模型 ID | 首字延迟 | 吞吐 | 上下文 | 定位 |")
            print("| :--- | :---: | :---: | :---: | :---: |")

            for m_id, m_info, st in v["alive_models"]:
                lat_str = format_latency(st.get("latency_ms"))
                tps = st.get("tps")
                tps_str = f"{tps} tok/s" if tps and tps > 0 else "-"
                verdict_str = format_verdict_tag(st.get("verdict"))
                ctx_str = format_context_spec(m_info.get("known_specs", {}))
                print(f"| `{m_id}` | {lat_str} | {tps_str} | {ctx_str} | {verdict_str} |")
            print()

    # 底部说明与推荐
    all_alive = []
    for v in valid_vendors:
        for m_id, m_info, st in v["alive_models"]:
            all_alive.append({
                "model_id": m_id,
                "vendor": v["vendor_id"],
                "verdict": st.get("verdict", "unknown"),
                "tps": st.get("tps") or 0,
                "latency_ms": st.get("latency_ms") or 9999
            })

    def rank_key(item):
        v_score = 2 if item["verdict"] == "primary" else (1 if item["verdict"] == "fallback" else 0)
        return (v_score, item["tps"], -item["latency_ms"])

    top_models = sorted(all_alive, key=rank_key, reverse=True)[:3]
    top_str = ", ".join([f"`{m['model_id']}` ({format_latency(m['latency_ms'])})" for m in top_models]) if top_models else "暂无"

    print("---")
    print(f"- 💡 **今日推荐主力 (Top 3)**: {top_str}")
    if filtered_vendors:
        filtered_str = ", ".join([f"`{fv['vendor_id']}` ({fv['reason']})" for fv in filtered_vendors])
        print(f"- 🚫 **已自动剔除失效供应商**: {filtered_str}")
    else:
        print("- 🚫 **已自动剔除失效供应商**: 无（全线存活）")

    print("- 📌 **快捷指令**: 查看完整排行榜 `fm 榜单` ｜ 即时测试 `fm测` ｜ 应用排位 `fm换` ｜ 指令大全 `fm指令`\n")
    return True


def do_top(config, limit=5):
    """查询今日高性价比免费主力 Top 榜单（原生 Markdown 表格）"""
    from datetime import datetime, timezone, timedelta
    tz_bj = timezone(timedelta(hours=8))
    today_bj = datetime.now(tz_bj).strftime("%Y-%m-%d")

    defaults = config.get("defaults", {})
    radar_db = defaults.get("sqlite_db", "/home/linxuan/.hermes/data/model-radar.sqlite")
    status_map = get_radar_models_status(radar_db)
    vendors = config.get("vendors", {})

    alive_candidates = []
    for v_key, v_info in vendors.items():
        v_models = v_info.get("models", {})
        for m_id, m_info in v_models.items():
            st = status_map.get(m_id)
            if not st or st.get("status") != "alive":
                continue

            specs = m_info.get("known_specs", {})
            alive_candidates.append({
                "model_id": m_id,
                "vendor_id": v_key,
                "vendor_name": v_info.get("name", v_key),
                "verdict": st.get("verdict", "unknown"),
                "latency_ms": st.get("latency_ms") or 9999,
                "tps": st.get("tps") or 0,
                "context": format_context_spec(specs),
                "stream_only": m_info.get("stream_only", v_info.get("stream_only", False)),
                "updated_at": st.get("updated_at", "-")
            })

    def rank_key(item):
        v_score = 2 if item["verdict"] == "primary" else (1 if item["verdict"] == "fallback" else 0)
        return (v_score, item["tps"], -item["latency_ms"])

    ranked_models = sorted(alive_candidates, key=rank_key, reverse=True)
    top_models = ranked_models[:limit]

    print(f"### 🏆 今日高性价比免费主力 Top {len(top_models)} 榜单（{today_bj}）\n")
    print("> **基准口径**：存活 (`alive`) 优先 > 定位 (`primary`) 优先 > 吞吐 (`tps`) 降序 > 首字延时升序\n")

    if not top_models:
        print("> ⚠️ 当前暂无处于存活状态的候选模型！请先运行 `fm测` 触发巡检。\n")
    else:
        print("| 排名 | 模型 ID | 供应商 | 首字延迟 | 吞吐 | 上下文 | 定位 |")
        print("| :---: | :--- | :--- | :---: | :---: | :---: | :---: |")

        medals = ["🥇", "🥈", "🥉", "4", "5", "6", "7", "8", "9", "10"]
        for idx, m in enumerate(top_models):
            rank_label = medals[idx] if idx < len(medals) else str(idx + 1)
            lat_str = format_latency(m["latency_ms"])
            tps_str = f"{m['tps']} tok/s" if m["tps"] and m["tps"] > 0 else "-"
            verdict_str = format_verdict_tag(m["verdict"])
            print(f"| {rank_label} | `{m['model_id']}` | {m['vendor_name']} | {lat_str} | {tps_str} | {m['context']} | {verdict_str} |")

    print("\n💡 **提示**：运行 `fm换 yangmao` 可直接将优质主力排位同步至 10Router 网关；查看全部运行 `fm指令`。\n")
    return True


def do_investigate(config, vendor=None, model=None):
    """【第一主位】查/探查：四环流水线
    ① 📡 前哨一手动态货架发现（直连官方客户端推荐接口）；
    ② 🔍 10Router 现网差集对拍（双向匹配、外部新发现、网关幽灵挂载）；
    ③ ⚡ 现场真流量探活并入库（识别 200 稳活、402 额度尽、404 下架、超时）；
    ④ 💡 决策与换血建议（提示补录新发现模型、剔除幽灵模型、一键同步排位）。
    """
    defaults = config.get("defaults", {})
    gateway_url = defaults.get("gateway_url", "http://127.0.0.1:20128")
    router_db = defaults.get("router_db", "/home/linxuan/.10router-bare-data/db/data.sqlite")
    radar_db = defaults.get("sqlite_db", "/home/linxuan/.hermes/data/model-radar.sqlite")
    api_key = get_router_key(router_db)
    chat_endpoint = f"{gateway_url.rstrip('/')}/v1/chat/completions"

    vendors = config.get("vendors", {})
    target_vendors = []
    if vendor:
        v_list = [v.strip().lower() for v in vendor.split(",") if v.strip()]
        for v_item in v_list:
            for v_key in vendors:
                if v_item == v_key.lower() or v_item in v_key.lower():
                    if v_key not in target_vendors:
                        target_vendors.append(v_key)
        if not target_vendors and not model:
            model = vendor
            target_vendors = list(vendors.keys())
    else:
        target_vendors = list(vendors.keys())

    from datetime import datetime, timezone, timedelta
    tz_bj = timezone(timedelta(hours=8))
    today_bj = datetime.now(tz_bj).strftime("%Y-%m-%d")

    print(f"### 🧭 免费模型前哨嗅探与网关对拍报告（{today_bj}）\n")
    print("> 💡 执行模式：**前哨四环联动流水线**（① 📡 官方动态货架一手发现 ➔ ② 🔍 10Router 现网硬核差集对拍 ➔ ③ ⚡ 现场真流量探活入库 ➔ ④ 💡 换血决策建议）\n")

    for v_key in target_vendors:
        if v_key not in vendors:
            continue
        v_info = vendors[v_key]
        doc_url = v_info.get("doc_url", "")
        events_url = v_info.get("events_url", "")
        stream_only = v_info.get("stream_only", False)
        stream_tag = " · 仅流式" if stream_only else ""

        print(f"#### 🏢 [{v_key}] {v_info.get('name', v_key)}{stream_tag}\n")

        # 环 1：📡 前哨一手动态货架发现
        shelf_res = sniff_vendor_shelf(v_info)
        ext_free = shelf_res.get("free_models", [])
        ext_promotional = shelf_res.get("promotional_models", [])
        or_free = shelf_res.get("openrouter_free", [])
        disc_type = shelf_res.get("discovery_type", "unknown")

        # 环 2：🔍 10Router 现网硬核差集对拍
        candidate_ext = list(ext_free)
        if v_key == "cline":
            candidate_ext.extend(["qwen/qwen3.8-27b:free", "poolside/laguna-s-2.1:free"])

        gateway_binding = v_info.get("gateway_binding")
        cc = cross_check_gateway(v_key, candidate_ext, router_db, gateway_binding=gateway_binding)

        print("##### 📡 环 1 · 官方一手动态前哨探查")
        if shelf_res.get("ok"):
            # 标明一手探测源
            if disc_type == "package_introspect":
                pkg_ver = shelf_res.get("version") or "unknown"
                pub_time = shelf_res.get("publish_time") or "未知"
                print(f"- 📦 **官方一手源**: NPM 生产发版 (`v{pkg_ver}` · 发布于 {pub_time})")
            elif disc_type == "dynamic_shelf":
                print(f"- 🌐 **官方一手源**: 官方动态推荐接口 (`dynamic_shelf`)")
            elif disc_type == "doc_table":
                print(f"- 📄 **官方一手源**: 官方规约文档与活动站 (`doc_table`)")
            elif disc_type == "openapi":
                print(f"- 🔌 **官方一手源**: 官方 OpenAPI /v1/models 接口")
            else:
                print(f"- 📡 **官方一手源**: 官方文档页面探测 (`{disc_type}`)")

            if ext_free:
                free_preview = ", ".join([f"`{m}`" for m in ext_free[:8]])
                suffix = f"... (共 {len(ext_free)} 款)" if len(ext_free) > 8 else f" (共 {len(ext_free)} 款)"
                print(f"- 🟢 **官方当期货架/模型清单**: {free_preview}{suffix}")
            else:
                print(f"- 🟢 **官方当期货架/模型清单**: 暂未枚举到独立原子模型")

            if or_free:
                or_preview = ", ".join([f"`{m}`" for m in or_free[:4]])
                print(f"- 🌐 **OpenRouter 开放免费池**: {or_preview}... (共 {len(or_free)} 款)")
            if ext_promotional:
                promo_sample = ", ".join([f"`{m}`" for m in ext_promotional[:3]])
                print(f"- 🏷️ **促销体验/体验额度池**: {promo_sample}... (说明：须账号带体验余额，老账号额度用尽报 HTTP 402)")
            if shelf_res.get("events_summary"):
                events_str = "；".join(shelf_res["events_summary"][:3])
                print(f"- 🎁 **官方限免/活动政策**: {events_str}")
            if shelf_res.get("context_hints"):
                print(f"- 📏 **官方规约规格线索**: 上下文 " + ", ".join(shelf_res["context_hints"]))
            print()
        else:
            err_msg = ", ".join(shelf_res.get("errors", [])) or "未知探测错误"
            doc_link_str = f"[{doc_url}]({doc_url})" if doc_url.startswith("http") else doc_url
            print(f"- 🌐 **官方入口**: {doc_link_str} · 前哨探测异常: `{err_msg}`\n")
        print("##### 🔍 环 2 · 10Router 现网硬核差集对拍")
        if "error" in cc:
            print(f"- ⚠️ **网关对拍失败**: {cc['error']}\n")
        else:
            # 底层账号状态
            tot_acc = cc.get("total_accounts", 0)
            act_acc = cc.get("active_accounts", 0)
            if cc.get("warning_no_active"):
                acc_status_str = f"🔴 **全未激活预警**（登记 {tot_acc} 个账号，活跃 0 个！所有请求将报 404 No active credentials）"
            elif tot_acc > 0:
                acc_status_str = f"🟢 **正常**（登记 {tot_acc} 个账号，活跃 {act_acc} 个）"
            else:
                acc_status_str = "⚪ 未在 10Router 登记任何该供应商连接"
            print(f"- 👥 **底层账号激活状态**: {acc_status_str}")

            dm_str = ", ".join([f"`{m}`" for m in cc["dual_matched"][:8]]) if cc["dual_matched"] else "无"
            if len(cc["dual_matched"]) > 8:
                dm_str += f"... (共 {len(cc['dual_matched'])} 款)"

            nd_str = ", ".join([f"`{m}`" for m in cc["newly_discovered"][:8]]) if cc["newly_discovered"] else "无（现网已完整覆盖）"
            if len(cc["newly_discovered"]) > 8:
                nd_str += f"... (共 {len(cc['newly_discovered'])} 款)"

            gh_str = ", ".join([f"`{m}`" for m in cc["ghost_mounted"][:6]]) if cc["ghost_mounted"] else "无（无残留幽灵）"
            if len(cc["ghost_mounted"]) > 6:
                gh_str += f"... (共 {len(cc['ghost_mounted'])} 款)"

            print(f"- 🤝 **双向匹配 (Dual Matched)**: {dm_str}")
            print(f"- 🆕 **外部新发现漏配 (Newly Discovered)**: {nd_str}")
            print(f"- 👻 **网关幽灵挂载 (Ghost Mounted)**: {gh_str}\n")

        # 环 3：⚡ 现场真流量探活并入库
        print("##### ⚡ 环 3 · 现场真流量实测与入库快照")
        v_models = v_info.get("models", {})
        print("| 模型 ID | 实测状态 | 响应延迟 | 标称上下文 | 诊断与凭证 |")
        print("| :--- | :---: | :---: | :---: | :--- |")

        for m_id, m_info in v_models.items():
            if model and (model.lower() != m_id.lower() and model.lower() not in m_id.lower()):
                continue

            m_stream = m_info.get("stream_only", stream_only)
            # 现场发包打流量
            probe_res = probe_l1_heartbeat(chat_endpoint, api_key, m_id, stream_only=m_stream)
            # 实时入库持久化（冲刷掉 unknown）
            save_probe_result(radar_db, m_id, v_key, probe_res, m_info.get("known_specs"))

            # 诊断文案
            http_code = probe_res.get("http_code", 0)
            latency_ms = probe_res.get("latency_ms", 0)
            lat_str = f"**{round(latency_ms / 1000.0, 1)}s**" if latency_ms > 0 else "-"
            ctx_str = format_context_spec(m_info.get("known_specs", {}))
            err_text = probe_res.get("error") or ""

            if probe_res.get("alive"):
                status_icon = "🟢 稳活 (200)"
                first_s = probe_res.get("first_s")
                first_s_str = f"首字 {first_s}s" if first_s else "流式通畅"
                diag = f"响应通畅 ({first_s_str})"
            elif http_code == 402 or "insufficient_credits" in err_text.lower():
                status_icon = "🟡 额度尽 (402)"
                diag = "促销/体验额度耗尽 (ClinePass promotion exhausted，非下架)"
            elif http_code == 404:
                status_icon = "🔴 下架 (404)"
                if "No active credentials" in err_text:
                    diag = "10Router 无有效激活凭据/账号未登录"
                else:
                    diag = f"官方货架已下架或端点未找到"
            elif http_code == 429 or "rate limit" in err_text.lower():
                status_icon = "🟡 限流 (429)"
                diag = "触发供应商频率/并发限制，稍后重试"
            elif latency_ms >= 10000 or http_code == 0:
                status_icon = "⏱️ 超时 (Timeout)"
                diag = "上游接口超时（>10s），网络拥堵或被阻断"
            else:
                status_icon = f"🔴 异常 ({http_code})"
                diag = err_text[:50] if err_text else "连接失败"

            print(f"| `{m_id}` | {status_icon} | {lat_str} | {ctx_str} | {diag} |")

        # 环 4：💡 决策与换血建议
        print("\n##### 💡 环 4 · 运维决策与换血指引")
        advice_list = []
        if cc.get("warning_no_active"):
            advice_list.append(f"【严重风险】该供应商下登记的 {cc.get('total_accounts')} 个账号全部处于未激活/未登录状态，所有模型请求均会报 404 No active credentials，请先在 10Router 激活账号")
        if cc.get("ghost_mounted"):
            ghost_names = [f"`{m}`" for m in cc["ghost_mounted"][:4]]
            advice_list.append(f"发现 {len(cc['ghost_mounted'])} 个网关幽灵模型（如 {', '.join(ghost_names)}），官方当期已下架，建议在网关剔除或下线")
        if cc.get("newly_discovered"):
            new_names = [f"`{m}`" for m in cc["newly_discovered"][:4]]
            alias_pfx = gateway_binding.get("alias_prefixes", [v_key])[0] if gateway_binding else v_key
            advice_list.append(f"前哨嗅探到新上架/新发现模型 {', '.join(new_names)} 等共 {len(cc['newly_discovered'])} 款，建议及时补录至 10Router 网关（前缀如 `{alias_pfx}/`）")
        if not advice_list:
            advice_list.append("外部货架与 10Router 网关挂载高度对齐，无漏配与幽灵模型")

        for adv in advice_list:
            print(f"- 📌 {adv}")
        print("- 🚀 运行 `fm换 yangmao` 可将当期实测稳活的高性价比模型排位一键同步至网关 combos。")
        print("\n---\n")

    return True


def do_query(config, vendor=None, model=None):
    """查询并格式化输出供应商及模型运行与规约数据（原生 Markdown 表格）"""
    defaults = config.get("defaults", {})
    radar_db = defaults.get("sqlite_db", "/home/linxuan/.hermes/data/model-radar.sqlite")
    status_map = get_radar_models_status(radar_db)
    vendors = config.get("vendors", {})

    print("### 🔍 free-model-radar 模型大盘与规约状态\n")

    target_vendors = []
    if vendor:
        v_list = [v.strip().lower() for v in vendor.split(",") if v.strip()]
        for v_item in v_list:
            for v_key in vendors:
                if v_item == v_key.lower() or v_item in v_key.lower():
                    if v_key not in target_vendors:
                        target_vendors.append(v_key)
        if not target_vendors and not model:
            model = vendor
            target_vendors = list(vendors.keys())
    else:
        target_vendors = list(vendors.keys())

    matched_count = 0
    for v_key in target_vendors:
        if v_key not in vendors:
            continue
        v_info = vendors[v_key]
        vendor_header_printed = False

        for m_id, m_info in v_info.get("models", {}).items():
            if model and (model.lower() != m_id.lower() and model.lower() not in m_id.lower()):
                continue

            if not vendor_header_printed:
                doc_link = f"[{v_info.get('doc_url', 'N/A')}]({v_info.get('doc_url', 'N/A')})" if str(v_info.get('doc_url', '')).startswith("http") else v_info.get('doc_url', 'N/A')
                stream_tag = " · 仅流式" if v_info.get("stream_only", False) else ""
                print(f"##### 🏢 [{v_key}] {v_info.get('name', v_key)} (文档: {doc_link}{stream_tag})\n")
                print("| 模型 ID | 状态 | 首字延迟 | 吞吐 | 上下文 | 定位 |")
                print("| :--- | :---: | :---: | :---: | :---: | :---: |")
                vendor_header_printed = True

            matched_count += 1
            st = status_map.get(m_id, {})
            status_tag = st.get("status", "unknown")
            if status_tag == "alive":
                status_icon = "🟢 alive"
            elif status_tag == "dead":
                status_icon = "🔴 dead"
            else:
                status_icon = "⚪ unknown"

            lat_str = format_latency(st.get("latency_ms"))
            tps = st.get("tps")
            tps_str = f"{tps} tok/s" if tps and tps > 0 else "-"
            ctx_str = format_context_spec(m_info.get("known_specs", {}))
            verdict_str = format_verdict_tag(st.get("verdict"))

            print(f"| `{m_id}` | {status_icon} | {lat_str} | {tps_str} | {ctx_str} | {verdict_str} |")

        if vendor_header_printed:
            print()

    if matched_count == 0:
        print(f"> ⚠️ 未找到匹配供应商 `{vendor}` 或模型 `{model}` 的记录。\n")
    return True



def do_add_vendor(config, vendor, doc_url="", models=None, config_path=None):
    """向 vendors.yaml 添加供应商或模型"""
    if not vendor:
        print("❌ 错误：必须指定供应商名称 (--vendor)")
        return False

    cfg_path = get_config_path(config_path)
    if not os.path.exists(cfg_path):
        print(f"❌ 配置文件不存在: {cfg_path}")
        return False

    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if "vendors" not in data:
        data["vendors"] = {}

    v_entry = data["vendors"].setdefault(vendor, {
        "vendor_id": vendor,
        "name": vendor,
        "doc_url": doc_url or f"https://{vendor}.com",
        "stream_only": False,
        "models": {}
    })

    if doc_url:
        v_entry["doc_url"] = doc_url

    models_list = models if isinstance(models, list) else ([m.strip() for m in models.split(",") if m.strip()] if models else [])
    added_models = []
    for m in models_list:
        if m not in v_entry["models"]:
            v_entry["models"][m] = {
                "model_id": m,
                "stream_only": v_entry.get("stream_only", False),
                "known_specs": {
                    "pricing": "free"
                }
            }
            added_models.append(m)

    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    print(f"✅ 成功添加/更新供应商 [{vendor}] 到 {cfg_path}")
    if added_models:
        print(f"   已登记新模型: {', '.join(added_models)}")
    return True


def do_remove_vendor(config, vendor, config_path=None):
    """从 vendors.yaml 中移除指定供应商"""
    if not vendor:
        print("❌ 错误：必须指定供应商名称 (--vendor)")
        return False

    cfg_path = get_config_path(config_path)
    if not os.path.exists(cfg_path):
        print(f"❌ 配置文件不存在: {cfg_path}")
        return False

    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    vendors = data.get("vendors", {})
    if vendor not in vendors:
        print(f"⚠️ 供应商 [{vendor}] 在配置中未找到，无需移除。")
        return True

    del vendors[vendor]
    data["vendors"] = vendors

    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    print(f"✅ 已成功移除供应商 [{vendor}]，配置文件已同步更新。")
    return True


def do_heartbeat(config, vendor=None, model=None):
    """运行 L1 极轻心跳巡检"""
    defaults = config.get("defaults", {})
    gateway_url = defaults.get("gateway_url", "http://127.0.0.1:20128")
    router_db = defaults.get("router_db", "/home/linxuan/.10router-bare-data/db/data.sqlite")
    radar_db = defaults.get("sqlite_db", "/home/linxuan/.hermes/data/model-radar.sqlite")

    api_key = get_router_key(router_db)
    chat_endpoint = f"{gateway_url.rstrip('/')}/v1/chat/completions"

    print("=== 正在运行 L1 极轻心跳巡检 ===")
    vendors = config.get("vendors", {})
    
    # 模糊/精确匹配供应商列表
    target_vendors = []
    if vendor:
        for v_key in vendors:
            if vendor.lower() == v_key.lower() or vendor.lower() in v_key.lower():
                target_vendors.append(v_key)
        # 如果 vendor 参数可能其实是一个模型名（如 fm测 qoder），自动也尝试模型匹配
        if not target_vendors and not model:
            model = vendor
            target_vendors = list(vendors.keys())
    else:
        target_vendors = list(vendors.keys())

    results = []
    for v_key in target_vendors:
        if v_key not in vendors:
            print(f"⚠️ 警告：未识别的供应商 {v_key}")
            continue
        v_info = vendors[v_key]
        v_stream_only = v_info.get("stream_only", False)
        for m_id, m_info in v_info.get("models", {}).items():
            if model and (model.lower() != m_id.lower() and model.lower() not in m_id.lower()):
                continue
            stream_only = m_info.get("stream_only", v_stream_only)
            print(f"-> 探测模型: [{v_key}] {m_id} ...", end=" ", flush=True)
            probe_res = probe_l1_heartbeat(chat_endpoint, api_key, m_id, stream_only=stream_only)
            print(f"HTTP {probe_res['http_code']} | 存活: {probe_res['alive']} | 耗时: {probe_res['latency_ms']}ms")
            save_probe_result(radar_db, m_id, v_key, probe_res, m_info.get("known_specs"))
            results.append(probe_res)

    print("\n=== L1 心跳巡检完成，数据已入库 ===")
    return True



def do_benchmark(config, model=None, skip_ratelimit=False):
    """运行 L2 规约校准与深测（规约优先）"""
    if not model:
        print("❌ 错误：L2 深测模式必须使用 --model 指定具体模型")
        return False

    defaults = config.get("defaults", {})
    gateway_url = defaults.get("gateway_url", "http://127.0.0.1:20128")
    router_db = defaults.get("router_db", "/home/linxuan/.10router-bare-data/db/data.sqlite")
    radar_db = defaults.get("sqlite_db", "/home/linxuan/.hermes/data/model-radar.sqlite")

    api_key = get_router_key(router_db)
    chat_endpoint = f"{gateway_url.rstrip('/')}/v1/chat/completions"

    print("=== 正在运行 L2 规约校准与五维深测（规约优先） ===")
    known_specs = None
    vendor_name = "unknown"
    stream_only = False
    vendors = config.get("vendors", {})
    for v_key, v_info in vendors.items():
        if model in v_info.get("models", {}):
            vendor_name = v_key
            m_info = v_info["models"][model]
            known_specs = m_info.get("known_specs")
            stream_only = m_info.get("stream_only", v_info.get("stream_only", False))
            break

    print(f"模型: {model} | 供应商: {vendor_name} | 规约: {known_specs}")
    report = probe_l2_benchmark(
        chat_endpoint,
        api_key,
        model,
        known_specs=known_specs,
        stream_only=stream_only,
        skip_ratelimit=skip_ratelimit
    )
    save_probe_result(radar_db, model, vendor_name, report, known_specs)
    print("\n=== 测试完成，原始数据 ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return True


def do_apply(config, combo="yangmao", dry_run=False):
    """应用推荐排位到 10Router"""
    print(f"=== 正在执行 10Router combo [{combo}] 排位应用 (dry_run={dry_run}) ===")
    res = apply_combo_ranking(combo_name=combo, config=config, dry_run=dry_run)
    if not res.get("ok"):
        print(f"❌ 应用排位失败: {res.get('error')}")
        return False

    if res.get("dry_run"):
        print(f"🔍 [Dry-Run] 校验成功，快照备份预置于: {res.get('backup_file')}")
        print(f"   原排位: {res.get('previous_models')}")
        print(f"   拟排位: {res.get('new_models')}")
    else:
        print(f"🎉 成功更新 10Router combo [{combo}]！")
        print(f"   快照备份: {res.get('backup_file')}")
        print(f"   更新前: {res.get('previous_models')}")
        print(f"   更新后: {res.get('applied_models')}")
        print(f"   更新时间: {res.get('updated_at')}")
    return True


def main():
    parser = argparse.ArgumentParser(description="free-model-radar 免费模型雷达调度入口")
    parser.add_argument("--mode", choices=[
        "heartbeat", "benchmark", "crawl", "advise", "query", "investigate", "active", "top", "add-vendor", "remove-vendor", "apply", "help"
    ], required=True, help="运行模式")
    parser.add_argument("--vendor", help="指定供应商 (如 cline, qoder-cn, nvidia, amd)")
    parser.add_argument("--model", help="指定模型 ID (如 cline, qoder, nvidia/z-ai/glm-5.3-flash)")
    parser.add_argument("--combo", default="yangmao", help="10Router combo 名称 (默认 yangmao)")
    parser.add_argument("--doc-url", default="", help="添加供应商时的官方文档 URL")
    parser.add_argument("--models", help="逗号分隔的模型列表 (用于 add-vendor)")
    parser.add_argument("--config", help="自定义 vendors.yaml 路径")
    parser.add_argument("--dry-run", action="store_true", help="演练执行，不真正写入")
    parser.add_argument("--skip-ratelimit", action="store_true", help="跳过限流并发测试")

    args = parser.parse_args()
    config = load_config(args.config) if args.config else load_config()

    if args.mode in ("query", "investigate"):
        # 当指定供应商时触发四环前哨探查与对拍；若未指定则输出模型大盘规约快照
        if args.vendor or args.mode == "investigate":
            success = do_investigate(config, vendor=args.vendor, model=args.model)
        else:
            success = do_query(config, vendor=args.vendor, model=args.model)
        sys.exit(0 if success else 1)

    elif args.mode == "active":
        success = do_active(config)
        sys.exit(0 if success else 1)

    elif args.mode == "top":
        success = do_top(config)
        sys.exit(0 if success else 1)

    elif args.mode == "add-vendor":
        success = do_add_vendor(config, vendor=args.vendor, doc_url=args.doc_url, models=args.models, config_path=args.config)
        sys.exit(0 if success else 1)

    elif args.mode == "remove-vendor":
        success = do_remove_vendor(config, vendor=args.vendor, config_path=args.config)
        sys.exit(0 if success else 1)

    elif args.mode == "apply":
        success = do_apply(config, combo=args.combo, dry_run=args.dry_run)
        sys.exit(0 if success else 1)

    elif args.mode == "crawl":
        print("=== 正在运行双轨嗅探 ===")
        diff = sniffer_api_models(config)
        print(json.dumps(diff, ensure_ascii=False, indent=2))

        vendors = config.get("vendors", {})
        print("\n=== 官方文档轻量嗅探 ===")
        for v_key, v_info in vendors.items():
            doc_url = v_info.get("doc_url")
            print(f"[{v_key}] 嗅探 {doc_url} ...")
            res = sniffer_official_doc(doc_url)
            print(f"  结果: {res.get('ok')}, 线索: {res.get('context_hints', [])}")

    elif args.mode == "heartbeat":
        do_heartbeat(config, vendor=args.vendor, model=args.model)

    elif args.mode == "benchmark":
        do_benchmark(config, model=args.model, skip_ratelimit=args.skip_ratelimit)

    elif args.mode == "advise":
        print(f"=== 正在比对 10Router combo [{args.combo}] 并生成审批卡片 ===")
        diff = generate_combo_diff(args.combo, config)
        card = format_feishu_approval_card(diff)
        print("\n" + card + "\n")

    elif args.mode == "help":
        success = do_help(config)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
