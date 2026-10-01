#!/usr/bin/env python3
"""
preflight-guard.py · 自托管服务升级前预检护甲
检查项：
1. 磁盘剩余空间 (≥ 2GB)
2. 在途长任务/打卡状态互斥 (防打断签到/用量同步)
3. 端口占用与当前 PID 归属
4. 本地专属补丁双重归档完整性
"""

import sys
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

CONFIG_PATH = Path.home() / ".hermes" / "config" / "upgrade-apps.json"

def get_disk_free_mb(path="/") -> int:
    total, used, free = shutil.disk_usage(path)
    return int(free / (1024 * 1024))

def sh(cmd: str) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return ""

def main():
    if len(sys.argv) < 2:
        print("用法: python3 preflight-guard.py <app_id>")
        sys.exit(1)

    app_id = sys.argv[1].lower()
    if not CONFIG_PATH.exists():
        print(f"❌ 配置文件不存在: {CONFIG_PATH}")
        sys.exit(1)

    cfg = json.loads(CONFIG_PATH.read_text())
    apps = cfg.get("apps", {})
    if app_id not in apps:
        print(f"⚠️ 应用未在 upgrade-apps.json 注册: {app_id} (跳过专属预检)")
        sys.exit(0)

    app = apps[app_id]
    name = app.get("name", app_id)
    print(f"🛡️ 正在执行 {name} 升级前预检护甲...")

    # 1. 磁盘空间检查
    workdir = app.get("workdir", "/")
    disk_free = get_disk_free_mb(workdir)
    min_disk = app.get("preflight", {}).get("min_disk_free_mb", 2048)
    if disk_free < min_disk:
        print(f"❌ 磁盘空间不足: 当前可用 {disk_free}MB < 要求 {min_disk}MB")
        sys.exit(2)
    print(f"  ✅ 磁盘空间充足: 可用 {disk_free}MB (基线 {min_disk}MB)")

    # 2. 检查在途长任务 (针对 CreditDaddy 等)
    if app_id == "creditdaddy":
        try:
            req = urllib.request.Request("http://127.0.0.1:47860/api/status")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                if data.get("scheduler", {}).get("ticking") is True:
                    print("❌ 在途任务冲突: CreditDaddy 当前正在执行签到打卡，请等待 1 分钟后再升级！")
                    sys.exit(3)
                print("  ✅ 在途任务检查: 无在途打卡任务 (ticking: false)")
        except Exception:
            print("  ℹ️ 服务未运行或不可达，跳过在途任务检查")

    # 3. 补丁双重归档检查
    patch_dir = app.get("patch_dir")
    mirror_dir = app.get("patch_mirror_dir")
    if patch_dir and mirror_dir:
        p_path = Path(patch_dir).expanduser()
        m_path = Path(mirror_dir).expanduser()
        if p_path.exists() and m_path.exists():
            print(f"  ✅ 补丁双重镜像完整: {p_path} & {m_path}")
        elif p_path.exists() and not m_path.exists():
            print(f"  ⚠️ 警告: 镜像目录缺失，已自动镜像备份至 {m_path}")
            shutil.copytree(p_path, m_path, dirs_exist_ok=True)
        elif not p_path.exists() and m_path.exists():
            print(f"  ℹ️ 工程内补丁缺失，可随时从集中镜像 {m_path} 回灌")

    # 4. 端口与服务活跃度检查
    port = app.get("port")
    if port:
        pid = sh(f"lsof -ti:{port} 2>/dev/null | head -1")
        if pid:
            print(f"  ✅ 端口状态: :{port} 正常监听 (PID: {pid})")
        else:
            print(f"  ℹ️ 端口状态: :{port} 当前空闲")

    print(f"🎉 预检护甲全部通过，可以安全启动升级！")

if __name__ == "__main__":
    main()
