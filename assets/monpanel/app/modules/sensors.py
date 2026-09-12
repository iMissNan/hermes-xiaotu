"""温度传感器探测：优先 psutil.sensors_temperatures()，其次直接读 hwmon。

无任何传感器时返回 {"status": "N/A", "temperatures": []}，绝不抛异常。
"""
import glob
import os

import psutil


def _read_hwmon() -> list[dict]:
    """回退方案：直接扫描 /sys/class/hwmon/hwmon*/temp*_input（毫摄氏度）。"""
    temps = []
    for path in glob.glob("/sys/class/hwmon/hwmon*/temp*_input"):
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                continue
            celsius = int(raw) / 1000.0
        except (OSError, ValueError):
            continue  # 单个传感器读取失败不影响其余
        base = path[: -len("_input")]
        label = ""
        try:
            with open(base + "_label", encoding="utf-8") as f:
                label = f.read().strip()
        except OSError:
            pass
        chip = os.path.basename(os.path.dirname(path))
        temps.append(
            {"sensor": chip, "label": label, "current_c": round(celsius, 1)}
        )
    return temps


def collect() -> dict:
    """探测温度。返回 {"status", "count", "temperatures"}；无传感器 status="N/A"。"""
    try:
        raw = psutil.sensors_temperatures()
    except Exception:
        raw = None

    temps: list[dict] = []
    if raw:
        for chip, entries in raw.items():
            for e in entries:
                temps.append(
                    {
                        "sensor": chip,
                        "label": e.label or chip,
                        "current_c": e.current,
                        "high_c": e.high,
                        "critical_c": e.critical,
                    }
                )
        if temps:
            return {"status": "ok", "count": len(temps), "temperatures": temps}

    # psutil 无结果（权限/驱动原因）时回退直接读 hwmon
    temps = _read_hwmon()
    if temps:
        return {"status": "ok", "count": len(temps), "temperatures": temps}

    return {"status": "N/A", "temperatures": []}
