"""认证与会话：argon2id 密码校验、SQLite 会话签发/校验、登录限速、审计日志。"""
import logging
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status

from .config import (
    ADMIN_PASSWORD_HASH,
    AUDIT_LOG,
    LOGIN_RATE_LIMIT,
    RATE_LIMIT_WINDOW_SECONDS,
    SESSIONS_DB,
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
)

logger = logging.getLogger(__name__)

# argon2id：time_cost=3、memory_cost=64MiB、parallelism=4（OWASP 推荐档位）
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

# 登录限速状态：key = f"{ip}|{username}" -> 尝试时间戳队列（进程内滑动窗口）
_rate_lock = threading.Lock()
_rate_attempts: dict[str, deque[float]] = defaultdict(deque)
# 写接口（kill / 服务操作）通用限速：key = ip -> 时间戳队列
_generic_attempts: dict[str, deque[float]] = defaultdict(deque)


# ── 密码校验 ──────────────────────────────────────────────────────────
def verify_password(plain: str) -> bool:
    """校验明文是否匹配管理员 argon2id 哈希；异常一律视为校验失败。"""
    try:
        return _hasher.verify(ADMIN_PASSWORD_HASH, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


# ── 会话存储（SQLite，连接按操作即开即关）─────────────────────────────
def _connect() -> sqlite3.Connection:
    SESSIONS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SESSIONS_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表（幂等）。"""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                username   TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )


def create_session(username: str) -> str:
    """签发会话：32 字节随机 token（secrets.token_hex(32)），有效期 30 分钟。"""
    token = secrets.token_hex(32)
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, username, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (token, username, now, now + SESSION_TTL_SECONDS),
        )
    return token


def validate_session(token: str) -> str | None:
    """校验 token：先惰性删除全部过期行，再查未过期会话；返回 username 或 None。"""
    now = time.time()
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        row = conn.execute(
            "SELECT username FROM sessions WHERE token = ? AND expires_at > ?",
            (token, now),
        ).fetchone()
    return row["username"] if row else None


def revoke_session(token: str) -> None:
    """登出：撤销（删除）指定 token。"""
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ── 会话校验依赖（供 /api 下所有路由复用）─────────────────────────────
def get_current_user(request: Request) -> str:
    """从 Cookie 取 token 校验；缺失/无效/过期一律 401。"""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录"
        )
    username = validate_session(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="会话无效或已过期"
        )
    return username


# ── 登录限速（IP+用户名 双维度，每分钟 5 次）───────────────────────────
def is_rate_limited(ip: str, username: str) -> bool:
    """记录一次尝试并判断是否超限；超限返回 True（调用方回 429）。"""
    key = f"{ip}|{username}"
    now = time.time()
    with _rate_lock:
        q = _rate_attempts[key]
        # 滑出窗口的旧尝试丢弃（兼做内存回收）
        while q and now - q[0] > RATE_LIMIT_WINDOW_SECONDS:
            q.popleft()
        if len(q) >= LOGIN_RATE_LIMIT:
            return True
        q.append(now)
        return False


# ── 写接口通用限速（按 IP，每分钟 20 次）────────────────────────────────
GENERIC_RATE_LIMIT = 20


def is_generic_rate_limited(ip: str) -> bool:
    """写接口（kill / 服务操作）滑动窗口限速：超限返回 True（调用方回 429）。"""
    now = time.time()
    with _rate_lock:
        q = _generic_attempts[ip]
        while q and now - q[0] > RATE_LIMIT_WINDOW_SECONDS:
            q.popleft()
        if len(q) >= GENERIC_RATE_LIMIT:
            return True
        q.append(now)
        return False


# ── 审计日志 ──────────────────────────────────────────────────────────
def audit(event: str, ip: str, username: str, detail: str = "") -> None:
    """追加写入 data/audit.log：UTC 时间 | 事件 | IP | 用户名 | 详情。"""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"{ts}\t{event}\t{ip}\t{username}\t{detail}\n"
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        logger.exception("审计日志写入失败")
