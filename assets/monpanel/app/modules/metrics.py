"""2 秒采样历史缓冲：最近 60 个采样点（环形列表，进程内常驻）。

每次调用 collect() 采集一个新点并返回最近 60 点的序列视图，
供前端绘制 CPU / 内存 / 网络速率 / 磁盘 IO 的时间序列图。
"""
import threading
import time
from collections import deque

import psutil


MAX_POINTS = 60          # 环形缓冲容量
SAMPLE_INTERVAL = 2.0    # 期望采样间隔（秒），供前端参考

_lock = threading.Lock()
_buffer: deque[dict] = deque(maxlen=MAX_POINTS)  # maxlen 即环形裁剪

# 速率差分所需的上一帧状态
_prev_net: dict[str, tuple[int, int]] = {}
_prev_disk: tuple[int, int] | None = None
_prev_ts: float | None = None


def _sample() -> dict:
    """采集一个采样点：CPU% / 内存% / 全网卡 rx+tx 速率 / 全盘 IO 速率。"""
    global _prev_net, _prev_disk, _prev_ts

    now = time.time()
    net = psutil.net_io_counters(pernic=True)
    disk = psutil.disk_io_counters()

    rx_rate = tx_rate = 0.0
    disk_io = 0.0
    if _prev_ts is not None and now > _prev_ts:
        dt = now - _prev_ts
        for name, c in net.items():
            prev = _prev_net.get(name)
            if prev:
                rx_rate += max(0.0, (c.bytes_recv - prev[0]) / dt)
                tx_rate += max(0.0, (c.bytes_sent - prev[1]) / dt)
        if disk and _prev_disk:
            disk_io = (
                max(0.0, disk.read_bytes - _prev_disk[0])
                + max(0.0, disk.write_bytes - _prev_disk[1])
            ) / dt

    _prev_net = {name: (c.bytes_recv, c.bytes_sent) for name, c in net.items()}
    _prev_disk = (disk.read_bytes, disk.write_bytes) if disk else None
    _prev_ts = now

    return {
        "ts": now,
        "cpu": psutil.cpu_percent(interval=None),
        "memory": psutil.virtual_memory().percent,
        "net_rx": round(rx_rate, 2),
        "net_tx": round(tx_rate, 2),
        "disk_io": round(disk_io, 2),
    }


def collect() -> dict:
    """采集一个新点，返回最近 MAX_POINTS 点的按指标拆分的序列。"""
    with _lock:
        _buffer.append(_sample())
        points = list(_buffer)
    return {
        "interval_seconds": SAMPLE_INTERVAL,
        "max_points": MAX_POINTS,
        "timestamps": [p["ts"] for p in points],
        "cpu": [p["cpu"] for p in points],
        "memory": [p["memory"] for p in points],
        "net_rx": [p["net_rx"] for p in points],
        "net_tx": [p["net_tx"] for p in points],
        "disk_io": [p["disk_io"] for p in points],
    }
