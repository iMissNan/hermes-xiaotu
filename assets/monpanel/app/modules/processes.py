"""进程列表采集：psutil 快照，支持 cpu/mem 降序排序，最多返回 100 条。"""
import psutil

MAX_PROCESSES = 100
CMDLINE_MAX = 200


def collect(sort: str = "cpu") -> list[dict]:
    """返回进程快照列表。sort: cpu|mem，默认 cpu 降序；单进程失败自动跳过。"""
    # 预热：psutil 首次调用 cpu_percent(interval=None) 恒为 0.0，
    # 先扫一遍拿到基准值，第二轮采集才有真实增量
    for p in psutil.process_iter():
        try:
            p.cpu_percent(interval=None)
        except psutil.Error:
            pass

    attrs = (
        "pid",
        "name",
        "username",
        "cpu_percent",
        "memory_percent",
        "status",
        "cmdline",
    )
    rows: list[dict] = []
    for p in psutil.process_iter(attrs):
        try:
            info = p.info
            pid = info.get("pid")
            if pid is None:
                continue
            cmdline = info.get("cmdline") or []
            rows.append(
                {
                    "pid": pid,
                    "name": info.get("name") or "",
                    "username": info.get("username") or "",
                    "cpu_percent": round(float(info.get("cpu_percent") or 0.0), 2),
                    "memory_percent": round(float(info.get("memory_percent") or 0.0), 2),
                    "status": info.get("status") or "",
                    "cmdline": " ".join(cmdline)[:CMDLINE_MAX],
                }
            )
        except (psutil.Error, OSError, ValueError):
            # 进程可能在采集间隙退出，或 /proc 读取被拒——跳过即可
            continue

    key = "memory_percent" if sort == "mem" else "cpu_percent"
    rows.sort(key=lambda r: r[key], reverse=True)
    return rows[:MAX_PROCESSES]
