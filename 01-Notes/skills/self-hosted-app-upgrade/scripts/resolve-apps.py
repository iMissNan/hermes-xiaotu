#!/usr/bin/env python3
"""
resolve-apps.py · 应用名称模糊解析与拓扑排序器
输入：用户输入的模糊词或复合词（如 "cd, 10router", "积分管家 和 ai网关", "clash creditdaddy"）
输出：按基础设施依赖等级拓扑排序后的标准应用标识列表
"""

import sys
import json
import re
from pathlib import Path

CONFIG_PATH = Path.home() / ".hermes" / "config" / "upgrade-apps.json"

def resolve_app_tokens(raw_input: str) -> list[str]:
    if not CONFIG_PATH.exists():
        return []
    cfg = json.loads(CONFIG_PATH.read_text())
    apps = cfg.get("apps", {})
    ranks = cfg.get("topology_ranks", {"infra": 1, "gateway": 2, "service": 3, "dashboard": 4})

    # 分词：按逗号、顿号、空格、和、及、+ 等拆分
    tokens = [t.strip().lower() for t in re.split(r"[,，\s+、及和]+", raw_input) if t.strip()]
    
    matched_app_ids = set()
    for token in tokens:
        # 1. 直接匹配 ID
        if token in apps:
            matched_app_ids.add(token)
            continue
        # 2. 匹配别名与名称
        for app_id, data in apps.items():
            if token == data.get("name", "").lower():
                matched_app_ids.add(app_id)
                break
            aliases = [a.lower() for a in data.get("aliases", [])]
            if token in aliases:
                matched_app_ids.add(app_id)
                break
            # 包含匹配 (如 "10router升级" 提取出 "10router")
            if token.startswith(app_id) or any(token.startswith(a) for a in aliases):
                matched_app_ids.add(app_id)
                break

    # 拓扑排序：按 ranks 升序排列 (先 infra -> gateway -> service -> dashboard)
    sorted_apps = sorted(
        list(matched_app_ids),
        key=lambda aid: ranks.get(apps.get(aid, {}).get("tier", "service"), 99)
    )
    return sorted_apps

if __name__ == "__main__":
    if len(sys.argv) > 1:
        raw = " ".join(sys.argv[1:])
        res = resolve_app_tokens(raw)
        print(json.dumps(res, ensure_ascii=False))
    else:
        print("[]")
