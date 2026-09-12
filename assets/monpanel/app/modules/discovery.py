"""局域网设备发现：优先 arp-scan（需要权限时尝试 sudo -n），不可用/失败回退 ip neigh。

返回 IP/MAC/主机名列表；结果内存缓存 5 分钟（TTL 300s），锁内读写。
"""
import ipaddress
import re
import shutil
import subprocess
import threading
import time

DEFAULT_NETWORK = os.environ.get("MONPANEL_DISCOVER_NET", "192.168.10.0/24")  # 文档示例网段，按自己内网改

_ARPS = shutil.which("arp-scan") or ""  # 本机未安装则为空，直接走回退链路
_IP = shutil.which("ip") or "ip"
_SUDO = shutil.which("sudo") or ""

_TIMEOUT = 15
_TTL = 300  # 缓存 5 分钟

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": []}

_ARP_RE = re.compile(
    r"^\s*(?:DUP:\s*)?(\d{1,3}(?:\.\d{1,3}){3})\s+"
    r"([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\s*(.*)$"
)
_NEIGH_RE = re.compile(
    r"^(\d{1,3}(?:\.\d{1,3}){3})\s+dev\s+\S+"
    r"(?:\s+lladdr\s+([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}))?"
)


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=_TIMEOUT)


def _parse_arp(stdout: str) -> list[dict]:
    """解析 arp-scan 输出：`IP \t MAC \t 厂商/主机名`，忽略表头/Starting 行。"""
    rows: list[dict] = []
    for line in stdout.splitlines():
        m = _ARP_RE.match(line)
        if not m:
            continue
        name = m.group(3).strip().strip("()")
        rows.append(
            {
                "ip": m.group(1),
                "mac": m.group(2).lower(),
                "hostname": "" if name in ("", "Unknown") else name,
            }
        )
    return rows


def _parse_neigh(stdout: str) -> list[dict]:
    """解析 `ip neigh` 输出；仅保留解析出 lladdr 的条目，无 MAC 的 FAILED 行跳过。"""
    rows: list[dict] = []
    for line in stdout.splitlines():
        m = _NEIGH_RE.match(line)
        if not m or not m.group(2):
            continue
        rows.append({"ip": m.group(1), "mac": m.group(2).lower(), "hostname": ""})
    return rows


def _scan_arp(network: str) -> list[dict] | None:
    """arp-scan 扫描；直接运行失败且 sudo 可用时带 sudo -n 重试。返回 None 表示彻底失败。"""
    if not _ARPS:
        return None
    attempts: list[list[str]] = [[_ARPS, network]]
    if _SUDO:
        attempts.append([_SUDO, "-n", _ARPS, network])
    for args in attempts:
        try:
            r = _run(args)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0:
            return _parse_arp(r.stdout or "")
    return None


def _scan_ip_neigh() -> list[dict] | None:
    """ip neigh 回退；命令不存在/超时/非零退出返回 None。"""
    try:
        r = _run([_IP, "neigh"])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return _parse_neigh(r.stdout or "")


def _normalize(rows: list[dict]) -> list[dict]:
    """按 IP 排序并去重。"""
    seen: set[str] = set()
    out: list[dict] = []
    for row in sorted(rows, key=lambda r: ipaddress.ip_address(r["ip"])):
        if row["ip"] in seen:
            continue
        seen.add(row["ip"])
        out.append(row)
    return out


def scan(network: str = DEFAULT_NETWORK) -> list[dict]:
    """返回局域网设备列表（ip/mac/hostname），结果缓存 5 分钟（TTL 300s）。

    链路：arp-scan（需权限时 sudo -n 重试）→ 失败回退 ip neigh；
    两条链路全部失败时返回旧缓存，无旧缓存则返回 []。仅成功结果写缓存。
    """
    now = time.time()
    with _lock:
        if _cache["ts"] and now - _cache["ts"] < _TTL:
            return list(_cache["data"])
        stale = list(_cache["data"])

    rows = _scan_arp(network)
    if rows is None:
        rows = _scan_ip_neigh()
    if rows is None:
        return stale

    rows = _normalize(rows)
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = rows
    return list(rows)
