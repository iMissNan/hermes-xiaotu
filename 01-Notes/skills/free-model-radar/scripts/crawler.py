#!/usr/bin/env python3
"""双轨 + 前哨独立发现与 10Router 差集对拍器（crawler.py）

核心能力：
1. 前哨独立发现引擎 (sniff_client_shelf)：
   - 直连官方客户端 API（如 Cline 动态货架 https://api.cline.bot/api/v1/ai/cline/recommended-models），走本地代理（http://127.0.0.1:7892）；
   - 嗅探 OpenRouter :free 池接口；
   - 提取当期真实 free 模型，与 clinePass/promotional 额度池严格区分。
2. 10Router 网关硬核差集对拍 (cross_check_gateway)：
   - 查询 10Router kv (cl|%, cline|%) 与 providerConnections 的 modelLock；
   - 严格计算三大差集：
     * dual_matched: 官方当期上架且网关已挂载（双向对齐）
     * newly_discovered: 官方一手新出、网关漏配（需要补录挂载）
     * ghost_mounted: 官方已下架、网关仍残留挂载（幽灵挂载，需剔除）
3. 原有 API 模型比对与官方文档嗅探兼容保留。
"""

import json
import os
import re
import urllib.request
import urllib.error
import yaml

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config/vendors.yaml")
LOCAL_PROXY_URL = "http://127.0.0.1:7892"


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
    req = urllib.request.Request(
        f"{gateway_url.rstrip('/')}/v1/models",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    return [m["id"] for m in data.get("data", [])]


def sniff_client_shelf(vendor_id="cline", proxy_url=LOCAL_PROXY_URL, timeout=10):
    """前哨独立发现引擎：直连官方客户端动态推荐接口与开放免费池"""
    ret = {
        "vendor_id": vendor_id,
        "ok": False,
        "free_models": [],
        "openrouter_free": [],
        "promotional_models": [],
        "raw_shelf": {},
        "errors": []
    }

    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else {}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))

    if vendor_id == "cline":
        # 1. 抓取 Cline 动态货架接口
        cline_api_url = "https://api.cline.bot/api/v1/ai/cline/recommended-models"
        req = urllib.request.Request(
            cline_api_url,
            headers={"User-Agent": "Cline/3.0.0 (compatible; FreeModelRadar/2.0)"}
        )
        for attempt in range(2):
            try:
                with opener.open(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    ret["ok"] = True
                    ret["raw_shelf"] = data

                    # 提取当期真正 free 货架
                    for item in data.get("free", []):
                        m_id = item.get("id")
                        if m_id and m_id not in ret["free_models"]:
                            ret["free_models"].append(m_id)

                    # 提取促销/体验额度池（clinePass / recommended）
                    for item in data.get("clinePass", []):
                        m_id = item.get("id")
                        if m_id and m_id not in ret["promotional_models"]:
                            ret["promotional_models"].append(m_id)

                    for item in data.get("recommended", []):
                        m_id = item.get("id")
                        if m_id and m_id not in ret["promotional_models"]:
                            ret["promotional_models"].append(m_id)
                    break
            except Exception as e:
                if attempt == 1:
                    ret["errors"].append(f"cline_dynamic_api: {str(e)}")

        # 2. 抓取 OpenRouter 开放免费池 (:free 列表)
        or_url = "https://openrouter.ai/api/v1/models"
        req_or = urllib.request.Request(
            or_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FreeModelRadar/2.0)"}
        )
        try:
            with opener.open(req_or, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for item in data.get("data", []):
                    m_id = item.get("id", "")
                    if m_id.endswith(":free") and m_id not in ret["openrouter_free"]:
                        ret["openrouter_free"].append(m_id)
        except Exception as e:
            ret["errors"].append(f"openrouter_api: {str(e)}")

    return ret


def cross_check_gateway(vendor_id, external_free_models, router_db_path):
    """10Router 现网差集对拍：计算双向对齐、新发现漏配、网关幽灵挂载三大差集"""
    import sqlite3

    if not os.path.exists(router_db_path):
        return {"error": f"router db not found: {router_db_path}"}

    db = sqlite3.connect(f"file:{router_db_path}?mode=ro", uri=True)

    # 1. 查询 kv 表中的 providerAlias 映射
    kv_models = set()
    prefix_patterns = ["cl|%", "cline|%"] if vendor_id == "cline" else [f"{vendor_id}|%"]
    for pat in prefix_patterns:
        for r in db.execute("SELECT key, value FROM kv WHERE key LIKE ?", (pat,)).fetchall():
            try:
                val = json.loads(r[1])
                mid = val.get("id", val.get("name", ""))
                if mid:
                    kv_models.add(mid)
            except Exception:
                pass

    # 2. 查询 providerConnections 表中属于该供应商连接的已挂载模型（modelLock_）
    conn_models = set()
    p_pat = "%cline%" if vendor_id == "cline" else f"%{vendor_id}%"
    for r in db.execute("SELECT data FROM providerConnections WHERE provider LIKE ?", (p_pat,)).fetchall():
        try:
            data = json.loads(r[0])
            for k in data.keys():
                if k.startswith("modelLock_"):
                    conn_models.add(k[len("modelLock_"):])
        except Exception:
            pass

    db.close()

    gateway_all = kv_models.union(conn_models)
    ext_set = set(external_free_models)

    # 规范化去除前缀辅助函数
    def norm(m):
        if "/" in m:
            prefix, rest = m.split("/", 1)
            if prefix in ("cl", "cline"):
                return rest
        return m

    norm_ext = {norm(m): m for m in ext_set}
    norm_gw = {norm(m): m for m in gateway_all}

    # dual_matched: 官方当期上架且网关已挂载（双向对齐）
    dual_matched_keys = sorted(list(set(norm_ext.keys()).intersection(set(norm_gw.keys()))))
    dual_matched = [norm_gw[k] for k in dual_matched_keys]

    # newly_discovered: 官方一手新出、网关漏配（外部有但网关全无）
    newly_discovered_keys = sorted(list(set(norm_ext.keys()) - set(norm_gw.keys())))
    newly_discovered = [norm_ext[k] for k in newly_discovered_keys]

    # ghost_mounted: 官方已下架、网关仍挂着（网关残存但当期货架已除名）
    ghost_mounted = []
    for k, orig in norm_gw.items():
        if k not in norm_ext:
            # 仅针对明确属于免费前缀或免费标记的模型，避免误伤付费全家桶
            if any(tag in k.lower() for tag in ["cline-free/", "stealth/", ":free"]):
                ghost_mounted.append(orig)
    ghost_mounted = sorted(ghost_mounted)

    return {
        "vendor_id": vendor_id,
        "dual_matched": dual_matched,
        "newly_discovered": newly_discovered,
        "ghost_mounted": ghost_mounted,
        "gateway_total_count": len(gateway_all),
        "external_total_count": len(ext_set)
    }


def sniffer_api_models(config=None):
    """轨 1：比对 10Router 网关中的所有模型与 vendors 配置"""
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

        # 匹配网关中属于该 vendor 的模型
        matched_in_gateway = set()
        for m in all_models:
            m_lower = m.lower()
            if v_key in m_lower or (v_key == "qoder-cn" and "qoder" in m_lower):
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


def sniffer_official_doc(url, timeout=10):
    """轨 2：轻量嗅探官方页面，提取规约线索"""
    if not url:
        return {"ok": False, "reason": "empty_url"}
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FreeModelRadar/1.0)"}
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
    print("=== 正在运行双轨与前哨对拍器 ===")
    sniff = sniff_client_shelf("cline")
    print(f"Cline 外部发现 Free 模型: {sniff['free_models']}")
    print(f"OpenRouter 外部发现 :free 模型数: {len(sniff['openrouter_free'])}")
    all_ext = sniff["free_models"] + ["qwen/qwen3.8-27b:free", "poolside/laguna-s-2.1:free"]
    cc = cross_check_gateway("cline", all_ext, "/home/linxuan/.10router-bare-data/db/data.sqlite")
    print(f"对拍结果 - 双向匹配: {cc['dual_matched']}")
    print(f"对拍结果 - 外部新发现: {cc['newly_discovered']}")
    print(f"对拍结果 - 幽灵挂载: {cc['ghost_mounted']}")
