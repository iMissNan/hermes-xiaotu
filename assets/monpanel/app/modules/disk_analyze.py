"""目录磁盘占用分析：后台线程统计目标目录的大小分布，返回按大小降序的前 20 项排行。

优先调用 `du --max-depth=1`，执行失败（命令缺失/超时/非零退出）时
回退到 Python os.walk 遍历累加。任务状态（running/done/error）与结果
存于进程内内存字典，key 为任务 id（uuid4 hex）；done/error 任务保留
10 分钟后被清理，防止无限增长。

对外接口：
- start(path) -> task_id：启动后台统计任务；path 非法（不存在/非目录）抛 ValueError
- get(task_id) -> dict：查询任务状态与结果；任务不存在返回含 code=404 的错误对象
"""

import os
import shutil
import subprocess
import threading
import time
import uuid

MAX_ITEMS = 20     # 排行最多返回前 20 项
CLEANUP_TTL = 600  # 已完成/失败任务保留 10 分钟后清理
DU_TIMEOUT = 60    # du 单次执行超时（秒），超时即回退 os.walk

_DU = shutil.which("du") or "du"

_lock = threading.Lock()
_tasks: dict[str, dict] = {}


def start(path: str) -> str:
    """启动一个后台目录统计任务，返回任务 id。

    path 必须是存在的目录，否则抛 ValueError（由 HTTP 层映射为 400）。
    """
    if not path or not os.path.isdir(path):
        raise ValueError(f"path is not an existing directory: {path!r}")

    task_id = uuid.uuid4().hex
    task = {
        "id": task_id,
        "path": os.path.abspath(path),
        "status": "running",
        "result": None,
        "error": None,
        "created": time.time(),
    }
    with _lock:
        _sweep_locked()
        _tasks[task_id] = task

    threading.Thread(
        target=_worker,
        args=(task_id, task["path"]),
        daemon=True,
        name=f"disk-analyze-{task_id[:8]}",
    ).start()
    return task_id


def get(task_id: str) -> dict:
    """查询任务状态与结果。

    任务不存在时返回 {"status": "not_found", "code": 404, "error": ...}，
    调用方可据此映射为 HTTP 404。
    """
    with _lock:
        task = _tasks.get(task_id)
        if task is None:
            return {
                "status": "not_found",
                "code": 404,
                "error": f"task {task_id!r} not found",
            }
        res = task["result"]
        return {
            "id": task["id"],
            "path": task["path"],
            "status": task["status"],
            "result": dict(res, items=list(res["items"])) if res else None,
            "error": task["error"],
        }


def _sweep_locked() -> None:
    """清理超过 CLEANUP_TTL 的 done/error 任务（调用方须持有 _lock）。"""
    cutoff = time.time() - CLEANUP_TTL
    stale = [
        tid
        for tid, tk in _tasks.items()
        if tk["status"] in ("done", "error") and tk["created"] < cutoff
    ]
    for tid in stale:
        del _tasks[tid]


def _worker(task_id: str, path: str) -> None:
    """后台统计线程：du → os.walk 回退，结果写入任务记录。"""
    try:
        du = _du_sizes(path)
        if du is None:
            total, rows = _walk_sizes(path)
        else:
            total, rows = du
        _finish(
            task_id,
            status="done",
            result={
                "total": total,
                "count": len(rows),
                "items": _rank(path, rows),
            },
        )
    except Exception as exc:  # 任何异常都落为 error，不悬挂 running
        _finish(task_id, status="error", error=f"{type(exc).__name__}: {exc}")


def _du_sizes(path: str) -> tuple[int, list[tuple[str, int, bool]]] | None:
    """`du -B1 --max-depth=1` 统计；返回 (总字节数, [(完整路径, 字节, 是否目录), ...])。

    命令缺失/超时/非零退出返回 None，由调用方走 os.walk 回退。
    """
    try:
        r = subprocess.run(
            [_DU, "-B1", "--max-depth=1", path],
            capture_output=True,
            text=True,
            timeout=DU_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None

    target = os.path.abspath(path)
    total = 0
    rows: list[tuple[str, int, bool]] = []
    for line in r.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        try:
            size = int(parts[0])
        except ValueError:
            continue
        p = parts[1]
        if os.path.abspath(p) == target:
            total = size  # du 的总计行
            continue
        rows.append((p, size, os.path.isdir(p)))
    return total, rows


def _walk_sizes(path: str) -> tuple[int, list[tuple[str, int, bool]]]:
    """os.walk 兜底：顶层子目录递归求和、目标目录下的直接文件计自身。

    无权限目录经 onerror 静默跳过；返回 (总字节数, [(完整路径, 字节, 是否目录), ...])。
    """
    base = os.path.abspath(path)
    top_dirs: set[str] = set()
    sizes: dict[str, int] = {}
    total = 0
    for root, dirs, files in os.walk(base, onerror=lambda _exc: None):
        rel = os.path.relpath(root, base)
        if rel == ".":
            top_dirs.update(dirs)
            top = None
        else:
            top = rel.split(os.sep, 1)[0]
        for name in files:
            fp = os.path.join(root, name)
            try:
                size = os.lstat(fp).st_size
            except OSError:
                size = 0
            total += size
            key = os.path.join(base, top) if top is not None else fp
            sizes[key] = sizes.get(key, 0) + size
    rows = [
        (p, sz, os.path.dirname(p) == base and os.path.basename(p) in top_dirs)
        for p, sz in sizes.items()
    ]
    return total, rows


def _rank(base: str, rows: list[tuple[str, int, bool]]) -> list[dict]:
    """归一化为相对路径名，按大小降序排序（同大小按名升序），取前 MAX_ITEMS 项。"""
    items = []
    for p, size, is_dir in rows:
        rel = os.path.relpath(p, base)
        items.append({"name": rel + "/" if is_dir else rel, "size": size, "is_dir": is_dir})
    items.sort(key=lambda it: (-it["size"], it["name"]))
    return items[:MAX_ITEMS]


def _finish(
    task_id: str,
    *,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    """写入任务终态；created 更新为完成时间，作为清理 TTL 起点。"""
    with _lock:
        task = _tasks.get(task_id)
        if task is None:
            return
        task["status"] = status
        task["result"] = result
        task["error"] = error
        task["created"] = time.time()
