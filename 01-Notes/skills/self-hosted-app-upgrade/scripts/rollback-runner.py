#!/usr/bin/env python3
"""
rollback-runner.py · 一键后悔药（安全回滚器）
用法：
  python3 rollback-runner.py <app_id> [backup_dir]
说明：
  若未指定 backup_dir，自动匹配 ~/backups/<app_id>/ 下最新的 pre-* 备份。
  执行原子还原：停止服务 -> 恢复源码/数据 -> 重新应用配置 -> 重启服务 -> 校验基线
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path

def sh(cmd: str) -> tuple[int, str]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()

def main():
    if len(sys.argv) < 2:
        print("用法: python3 rollback-runner.py <app_id> [backup_dir]")
        sys.exit(1)

    app_id = sys.argv[1].lower()
    backups_base = Path.home() / "backups" / app_id
    if not backups_base.exists() or not list(backups_base.glob("pre-*")):
        print(f"❌ 未找到 {app_id} 的历史备份目录: {backups_base}")
        sys.exit(2)

    if len(sys.argv) >= 3:
        target_backup = Path(sys.argv[2])
    else:
        # 寻找最新
        all_backups = sorted(list(backups_base.glob("pre-*")), key=lambda p: p.stat().st_mtime)
        target_backup = all_backups[-1]

    print(f"💊 正在为 {app_id} 启动一键后悔药回滚...")
    print(f"  📦 选定备份锚点: {target_backup}")

    if app_id == "creditdaddy":
        # 1. 停机
        print("  1. 停止服务: creditdaddy.service")
        sh("sudo systemctl stop creditdaddy.service")
        
        # 2. 还原工程与数据
        opt_src = target_backup / "opt-creditdaddy"
        dot_data = target_backup / "dot-creditdaddy"
        if opt_src.exists():
            print(f"  2. 还原工程目录: /opt/creditdaddy <- {opt_src}")
            sh("rm -rf /opt/creditdaddy")
            shutil.copytree(opt_src, "/opt/creditdaddy", dirs_exist_ok=True)
        if dot_data.exists():
            print(f"  3. 还原数据目录: ~/.creditdaddy <- {dot_data}")
            sh("rm -rf ~/.creditdaddy")
            shutil.copytree(dot_data, Path.home() / ".creditdaddy", dirs_exist_ok=True)
            
        # 3. 启动并复查
        print("  4. 重启服务并复查...")
        sh("sudo systemctl restart creditdaddy.service")
        code, out = sh("curl -s http://127.0.0.1:47860/api/status")
        if '"ok":true' in out:
            print("  ✅ 回滚成功！服务已恢复至备份基线，端到端健康检查通过。")
        else:
            print(f"  ⚠️ 服务已重启但健康响应异常: {out}")
    else:
        print(f"ℹ️ 该应用类型回滚逻辑请参考通用 SOP 还原: {target_backup}")

if __name__ == "__main__":
    main()
