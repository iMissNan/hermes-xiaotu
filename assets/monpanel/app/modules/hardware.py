"""硬件信息聚合：CPU / 内存 / 磁盘 / 网络 / 系统，返回统一 dict。

所有 psutil 调用均为尽力而为：单点失败不阻塞整包采集，
由上层路由负责 500 错误响应（本模块不抛异常堆栈）。
"""
import socket
import threading
import time
from datetime import datetime

import platform
import psutil


# ── 网络速率缓存：记录每个网卡上次累计字节数，用于差分算速率 ─────────
_net_cache: dict[str, dict] = {}
_net_lock = threading.Lock()


def _cpu_model() -> str | None:
    """从 /proc/cpuinfo 读 CPU 型号；非 Linux / 无权限返回 None。"""
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def _cpu() -> dict:
    freq = psutil.cpu_freq()
    return {
        "model": _cpu_model(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "frequency_mhz": round(freq.current, 1) if freq and freq.current else None,
        "usage_percent": psutil.cpu_percent(interval=None),
        "load_avg": [round(x, 2) for x in psutil.getloadavg()],
    }


def _memory() -> dict:
    m = psutil.virtual_memory()
    return {
        "total": m.total,
        "used": m.used,
        "available": m.available,
        "percent": m.percent,
    }


def _disk() -> list[dict]:
    mounts = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            # 挂载点不可访问（如权限受限）时跳过，不中断整包
            continue
        mounts.append(
            {
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            }
        )
    return mounts


def _network() -> list[dict]:
    counters = psutil.net_io_counters(pernic=True)
    now = time.time()
    result = []
    with _net_lock:
        for name, c in counters.items():
            prev = _net_cache.get(name)
            if prev and now - prev["ts"] > 0:
                dt = now - prev["ts"]
                rx_rate = max(0.0, (c.bytes_recv - prev["rx"]) / dt)
                tx_rate = max(0.0, (c.bytes_sent - prev["tx"]) / dt)
            else:
                rx_rate = tx_rate = 0.0  # 首次采样无历史，速率记 0
            _net_cache[name] = {"ts": now, "rx": c.bytes_recv, "tx": c.bytes_sent}
            result.append(
                {
                    "name": name,
                    "bytes_sent": c.bytes_sent,
                    "bytes_recv": c.bytes_recv,
                    "packets_sent": c.packets_sent,
                    "packets_recv": c.packets_recv,
                    "rx_bytes_per_sec": round(rx_rate, 2),
                    "tx_bytes_per_sec": round(tx_rate, 2),
                }
            )
    return result


def _system() -> dict:
    boot = psutil.boot_time()
    return {
        "hostname": socket.gethostname(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "arch": platform.machine(),
        "platform": platform.platform(),
        "boot_time": boot,
        "boot_time_iso": datetime.fromtimestamp(boot).isoformat(timespec="seconds"),
        "uptime_seconds": round(time.time() - boot, 1),
    }


def collect() -> dict:
    """聚合一次完整硬件快照。"""
    return {
        "timestamp": time.time(),
        "cpu": _cpu(),
        "memory": _memory(),
        "disk": _disk(),
        "network": _network(),
        "system": _system(),
    }
