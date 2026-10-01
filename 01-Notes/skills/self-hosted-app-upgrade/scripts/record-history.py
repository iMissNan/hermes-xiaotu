#!/usr/bin/env python3
"""
record-history.py · 升级与回滚台账轻量记录器
存储位置：~/.hermes/state/upgrade-history.jsonl
每一行为一次升级或回滚的审计条目（时间、应用、动作、旧版本、新版本、结果、耗时）
"""

import sys
import json
import time
from pathlib import Path

HISTORY_FILE = Path.home() / ".hermes" / "state" / "upgrade-history.jsonl"

def record_entry(app: str, action: str, from_ver: str, to_ver: str, status: str, duration_s: float, notes: str = ""):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S CST"),
        "app": app,
        "action": action, # upgrade | rollback | preflight
        "from_version": from_ver,
        "to_version": to_ver,
        "status": status, # SUCCESS | FAILED | BLOCKED
        "duration_s": round(duration_s, 2),
        "notes": notes
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"📝 审计台账已记入: {app} {action} -> {status}")

if __name__ == "__main__":
    if len(sys.argv) >= 6:
        record_entry(
            app=sys.argv[1],
            action=sys.argv[2],
            from_ver=sys.argv[3],
            to_ver=sys.argv[4],
            status=sys.argv[5],
            duration_s=float(sys.argv[6]) if len(sys.argv) > 6 else 0.0,
            notes=sys.argv[7] if len(sys.argv) > 7 else ""
        )
    else:
        print("用法: python3 record-history.py <app> <action> <from_ver> <to_ver> <status> [duration_s] [notes]")
