"""用户 systemd 服务查询与控制。

安全约定：
- 所有命令通过 subprocess 参数列表传参（systemctl --user ...），绝不走 shell 拼接
- unit 白名单：固定三项 + 用户服务目录实际存在的 unit
- action 白名单：start|stop|restart（由调用方校验，本模块不再重复放行）
"""
import os
import subprocess
from pathlib import Path

# 固定白名单：监控面板自身 + 本机已知用户服务
BASE_WHITELIST = {"monpanel.service", "jellyfin.service", "tailscaled.service"}
# 用户服务目录：新增 unit 后自动纳入白名单
USER_SERVICE_DIR = Path.home() / ".config" / "systemd" / "user"

ACTIONS = ("start", "stop", "restart")

_ACTION_TIMEOUT = 30
_LIST_TIMEOUT = 15


def _env() -> dict:
    """systemctl --user 需要 XDG_RUNTIME_DIR；从服务上下文启动时可能缺失，补默认值。"""
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return env


def _run(args: list[str], timeout: int = _ACTION_TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_env(),
    )


def whitelist() -> set[str]:
    """白名单 = 固定三项 ∪ 用户服务目录中的 *.service 文件名。"""
    units = set(BASE_WHITELIST)
    if USER_SERVICE_DIR.is_dir():
        units.update(p.name for p in USER_SERVICE_DIR.glob("*.service"))
    return units


def _parse_list_units(output: str) -> dict[str, dict]:
    """解析 `list-units --no-legend` 输出：前 4 列固定，剩余拼接为描述。"""
    parsed: dict[str, dict] = {}
    for line in output.splitlines():
        parts = line.split(None, 4)
        if not parts:
            continue
        parsed[parts[0]] = {
            "load": parts[1] if len(parts) > 1 else "",
            "active": parts[2] if len(parts) > 2 else "",
            "sub": parts[3] if len(parts) > 3 else "",
            "description": parts[4] if len(parts) > 4 else "",
        }
    return parsed


def is_active(unit: str) -> str:
    """回读 `systemctl --user is-active <unit>`；任何异常一律视为 unknown。"""
    try:
        r = _run(["is-active", unit], timeout=10)
        return (r.stdout or "").strip() or "unknown"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def list_services() -> list[dict]:
    """白名单内全部 unit 的状态列表；list-units 缺失的 unit 尽力补 is-active。"""
    try:
        r = _run(["list-units", "--type=service", "--all", "--no-legend"], timeout=_LIST_TIMEOUT)
        units = _parse_list_units(r.stdout or "")
    except (subprocess.SubprocessError, OSError):
        units = {}

    rows: list[dict] = []
    for unit in sorted(whitelist()):
        info = units.get(unit, {})
        state = is_active(unit)
        rows.append(
            {
                "unit": unit,
                "load": info.get("load") or "unknown",
                "active": info.get("active") or state,
                "sub": info.get("sub") or state,
                "description": info.get("description") or "",
                "is_active": state,
            }
        )
    return rows


def action(unit: str, action_name: str) -> str:
    """执行 start|stop|restart 并回读 is-active。unit/action 由调用方校验。"""
    _run([action_name, unit])
    return is_active(unit)
