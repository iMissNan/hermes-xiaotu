"""网络端口采集：ss -tulnp 解析，-p 失败/无权限时降级 ss -tuln。"""
import re
import shutil
import subprocess

_SS_PATH = shutil.which("ss") or "ss"
_PROC_RE = re.compile(r'"([^"]+)"')

_TIMEOUT = 15


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=_TIMEOUT)


def _parse_ports(stdout: str) -> list[dict]:
    rows: list[dict] = []
    for line in stdout.splitlines():
        parts = line.split()
        # 表头（Netid 开头）与畸形行直接跳过
        if not parts or parts[0].lower() == "netid" or len(parts) < 6:
            continue
        protocol = parts[0]
        local, peer = parts[4], parts[5]
        address, _, port = local.rpartition(":")
        try:
            port_num: str | int = int(port)
        except ValueError:
            port_num = port  # 解析失败保留原样（理论上不会发生）
        procs = _PROC_RE.findall(line)
        rows.append(
            {
                "protocol": protocol,
                "local_address": address,
                "local_port": port_num,
                "remote_address": peer,
                "process": ",".join(dict.fromkeys(procs)) if procs else "",
            }
        )
    return rows


def collect() -> list[dict]:
    """先 ss -tulnp（带进程名）；失败（命令不存在/无权限）降级 ss -tuln。"""
    try:
        r = _run([_SS_PATH, "-tulnp"])
        if r.returncode != 0:
            raise subprocess.SubprocessError(f"ss -tulnp 退出码 {r.returncode}")
    except (OSError, subprocess.SubprocessError):
        try:
            r = _run([_SS_PATH, "-tuln"])
        except (OSError, subprocess.SubprocessError):
            return []
    return _parse_ports(r.stdout or "")
