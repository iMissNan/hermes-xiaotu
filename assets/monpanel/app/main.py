"""monpanel 入口：FastAPI 骨架 + 鉴权路由 + 只读监控 + 管控 API。

- POST /api/login      免认证：限速 -> 校验密码 -> 签发 token -> 设置 Cookie
- POST /api/logout     需认证：撤销 token
- GET  /api/auth/check 需认证：200=已登录 / 401=未登录
- GET  /api/hardware|sensors|metrics  只读监控（需认证）
- GET  /api/processes        进程列表（需认证，?sort=cpu|mem）
- POST /api/processes/{pid}/kill   终止进程（需认证 + Origin 同源 + 二次密码）
- GET  /api/services        用户 systemd 服务状态（需认证）
- POST /api/services/{unit}/{action}  服务 start|stop|restart（同上三重防护）
- GET  /api/network/ports   端口监听列表（需认证）
- /api 下其余路由（后续步骤）统一挂在 api_router 上，默认经 get_current_user 保护
"""
import logging
import os
import signal
import subprocess
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import psutil
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth
from .config import (
    ADMIN_USERNAME,
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    STATIC_DIR,
)
from .modules import (
    discovery,
    disk_analyze,
    hardware,
    metrics,
    network,
    processes,
    sensors,
    services,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    auth.init_db()
    yield


STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="monpanel",
    docs_url=None,      # 生产环境关闭 Swagger/OpenAPI 文档
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class ReauthRequest(BaseModel):
    """高危写操作的二次确认体：password 缺失视为空串，统一按 re-auth 失败处理。"""
    password: str = Field(default="", max_length=256)


class DiskAnalyzeRequest(BaseModel):
    """磁盘分析请求体：path 为待统计目录。"""
    path: str = Field(..., min_length=1, max_length=4096)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ── 免认证路由：登录 ──────────────────────────────────────────────────
@app.post("/api/login")
def login(req: LoginRequest, request: Request):
    ip = _client_ip(request)

    # 1. 限速在密码校验之前：IP+用户名 双维度，每分钟 5 次
    if auth.is_rate_limited(ip, req.username):
        auth.audit("login_rate_limited", ip, req.username)
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "尝试过于频繁，请 1 分钟后再试"},
        )

    # 2. 校验凭据（统一报错文案，不泄露用户名是否存在）
    if req.username != ADMIN_USERNAME or not auth.verify_password(req.password):
        auth.audit("login_failed", ip, req.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    # 3. 签发会话并写审计
    token = auth.create_session(req.username)
    auth.audit("login_success", ip, req.username)

    resp = JSONResponse(content={"status": "ok", "username": req.username})
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_TTL_SECONDS,
        expires=SESSION_TTL_SECONDS,
        path="/",
        httponly=True,          # 脚本不可读
        secure=True,            # 仅 HTTPS 传输（8443 走 TLS）
        samesite="Strict",      # 禁止跨站携带，防 CSRF
    )
    return resp


# ── 受保护路由：/api 下所有路由默认经 get_current_user，未登录一律 401 ──
api_router = APIRouter(prefix="/api", dependencies=[Depends(auth.get_current_user)])


@api_router.post("/logout")
def logout(request: Request, username: str = Depends(auth.get_current_user)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        auth.revoke_session(token)
    auth.audit("logout", _client_ip(request), username)
    resp = JSONResponse(content={"status": "ok"})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@api_router.get("/auth/check")
def auth_check(username: str = Depends(auth.get_current_user)):
    return {"status": "ok", "username": username}


# ── 只读监控 API：全部经 get_current_user 保护，未登录一律 401 ────────
# 采集失败返回 500 + 简短 JSON，堆栈只进服务端日志，不泄露给客户端
def _monitor_error(name: str) -> None:
    logger.exception("%s 采集失败", name)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="监控数据采集失败，请稍后重试",
    )


@api_router.get("/hardware")
def get_hardware(username: str = Depends(auth.get_current_user)):
    try:
        return hardware.collect()
    except Exception:
        _monitor_error("hardware")


@api_router.get("/sensors")
def get_sensors(username: str = Depends(auth.get_current_user)):
    try:
        return sensors.collect()
    except Exception:
        _monitor_error("sensors")


@api_router.get("/metrics")
def get_metrics(username: str = Depends(auth.get_current_user)):
    try:
        return metrics.collect()
    except Exception:
        _monitor_error("metrics")


# ══════════════════════════════════════════════════════════════════════
# Phase 2 管控 API：只读端点走 get_current_user；高危写操作三重防护
#   （会话 401 → Origin 同源 403 → 二次密码 401），均写审计
# ══════════════════════════════════════════════════════════════════════
def _require_same_origin(request: Request) -> None:
    """Origin/Referer 必须非空且与请求 URL 同源（scheme+host+port），否则 403。"""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="缺少 Origin/Referer 头，拒绝请求"
        )
    ref = urlparse(origin)
    expected = urlparse(str(request.base_url))
    if (ref.scheme, ref.netloc) != (expected.scheme, expected.netloc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="跨源请求被拒绝"
        )


def _rate_limit_write(request: Request, username: str, target: str) -> None:
    """写接口通用限速 20 次/分钟（按 IP），超限 429 + 审计。"""
    ip = _client_ip(request)
    if auth.is_generic_rate_limited(ip):
        auth.audit("write_rate_limited", ip, username, target)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="操作过于频繁，请 1 分钟后再试",
        )


# ── 进程列表：GET /api/processes?sort=cpu|mem ─────────────────────────
@api_router.get("/processes")
def get_processes(
    sort: str = "cpu", username: str = Depends(auth.get_current_user)
):
    if sort not in ("cpu", "mem"):
        sort = "cpu"
    try:
        return processes.collect(sort)
    except Exception:
        _monitor_error("processes")


# ── 终止进程：POST /api/processes/{pid}/kill ──────────────────────────
@api_router.post("/processes/{pid}/kill")
def kill_process(
    pid: int,
    body: ReauthRequest,
    request: Request,
    username: str = Depends(auth.get_current_user),
):
    ip = _client_ip(request)
    target = f"pid={pid}"
    _rate_limit_write(request, username, target)
    _require_same_origin(request)

    # 二次密码确认（argon2 校验管理员口令），失败 401 + 审计
    if not auth.verify_password(body.password):
        auth.audit("process_kill_reauth_failed", ip, username, target)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="二次密码确认失败"
        )

    if pid <= 0:  # os.kill(0/负值) 会波及整个进程组，必须挡掉
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法 pid")

    auth.audit("process_kill_attempt", ip, username, target)
    try:
        if not psutil.pid_exists(pid):
            auth.audit("process_kill_result", ip, username, f"{target} result=not_found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="进程不存在")
        os.kill(pid, signal.SIGTERM)
    except PermissionError:
        auth.audit("process_kill_result", ip, username, f"{target} result=forbidden")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该进程")
    except ProcessLookupError:
        auth.audit("process_kill_result", ip, username, f"{target} result=not_found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="进程不存在")

    auth.audit("process_kill_result", ip, username, f"{target} result=ok")
    return {"status": "ok", "pid": pid}


# ── 服务状态：GET /api/services ───────────────────────────────────────
@api_router.get("/services")
def get_services(username: str = Depends(auth.get_current_user)):
    try:
        return services.list_services()
    except Exception:
        _monitor_error("services")


# ── 服务控制：POST /api/services/{unit}/{action} ──────────────────────
@api_router.post("/services/{unit}/{action}")
def service_action(
    unit: str,
    action: str,
    body: ReauthRequest,
    request: Request,
    username: str = Depends(auth.get_current_user),
):
    ip = _client_ip(request)
    target = f"unit={unit} action={action}"
    _rate_limit_write(request, username, target)
    _require_same_origin(request)

    # 白名单双校验：action 枚举 + unit 白名单（防注入；subprocess 参数列表传参）
    if action not in services.ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的操作：{action}（仅支持 start|stop|restart）",
        )
    if unit not in services.whitelist():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="unit 不在白名单内"
        )

    # 二次密码确认，失败 401 + 审计
    if not auth.verify_password(body.password):
        auth.audit("service_reauth_failed", ip, username, target)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="二次密码确认失败"
        )

    auth.audit("service_action_attempt", ip, username, target)
    try:
        state = services.action(unit, action)
    except (subprocess.SubprocessError, OSError):
        auth.audit("service_action_result", ip, username, f"{target} result=failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="systemctl 执行失败"
        )

    auth.audit("service_action_result", ip, username, f"{target} result=ok is_active={state}")
    return {"status": "ok", "unit": unit, "action": action, "is_active": state}


# ── 端口列表：GET /api/network/ports ──────────────────────────────────
@api_router.get("/network/ports")
def get_ports(username: str = Depends(auth.get_current_user)):
    try:
        return network.collect()
    except Exception:
        _monitor_error("network")


# ── 局域网设备发现：GET /api/network/devices ──────────────────────────
@api_router.get("/network/devices")
def get_network_devices(username: str = Depends(auth.get_current_user)):
    try:
        return {"devices": discovery.scan()}
    except Exception:
        _monitor_error("network discovery")


# ── 磁盘分析：POST /api/disk/analyze / GET /api/disk/analyze/{task_id} ─
@api_router.post("/disk/analyze")
def start_disk_analyze(
    body: DiskAnalyzeRequest,
    username: str = Depends(auth.get_current_user),
):
    try:
        task_id = disk_analyze.start(body.path)
    except ValueError as exc:  # path 不存在/非目录 -> 400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    return {"task_id": task_id}


@api_router.get("/disk/analyze/{task_id}")
def get_disk_analyze(
    task_id: str,
    username: str = Depends(auth.get_current_user),
):
    task = disk_analyze.get(task_id)
    if task.get("code") == 404:  # 任务不存在 -> 404
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=task["error"]
        )
    return {"status": task["status"], "results": task["result"], "error": task["error"]}


app.include_router(api_router)

# ── 免认证公开端点：导航页系统状态（只读百分比，无敏感信息）──────────
@app.get("/api/public/status")
def public_status():
    """Homepage 导航页接入：CPU/内存/磁盘使用率 + 在线时长。"""
    try:
        h = hardware.collect()
        disks = h.get("disk", []) or []
        root = next((d for d in disks if d.get("mountpoint") == "/"), None) or (disks[0] if disks else {})
        boot = h.get("system", {}).get("boot_time") or 0
        uptime_h = max(0, int(__import__("time").time() - boot)) // 3600 if boot else 0
        return {
            "cpu": h["cpu"].get("usage_percent"),
            "memory": h["memory"].get("percent"),
            "disk": root.get("percent"),
            "uptime_hours": uptime_h,
        }
    except Exception:
        return {"cpu": None, "memory": None, "disk": None, "uptime_hours": None}


# ── 静态资源 ──────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    index_html = STATIC_DIR / "index.html"
    if index_html.exists():
        return FileResponse(index_html)
    return {"service": "monpanel", "status": "running"}
