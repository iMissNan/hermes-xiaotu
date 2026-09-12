"""monpanel 配置常量：管理员凭据、会话、限速、监听、路径。"""
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
SESSIONS_DB = DATA_DIR / "sessions.db"
AUDIT_LOG = DATA_DIR / "audit.log"

# ── 管理员账户 ────────────────────────────────────────────────────────
ADMIN_USERNAME = "admin"
# argon2id 哈希（argon2-cffi，time_cost=3 / memory_cost=64MiB / parallelism=4）
# 首次部署必须生成自己的哈希：
#   python3 -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('<你的管理口令>'))"
# 然后写入环境变量 MONPANEL_ADMIN_HASH 或替换此处默认值
import os as _os
ADMIN_PASSWORD_HASH = _os.environ.get(
    "MONPANEL_ADMIN_HASH",
    "$argon2id$v=19$m=65536,t=3,p=4$<替换为你生成的argon2id哈希>",
)

# ── 会话 ──────────────────────────────────────────────────────────────
SESSION_COOKIE = "monpanel_session"
SESSION_TTL_SECONDS = 30 * 60  # 30 分钟

# ── 登录限速：每 IP+用户名 每分钟最多 5 次尝试 ────────────────────────
LOGIN_RATE_LIMIT = 5
RATE_LIMIT_WINDOW_SECONDS = 60

# ── 监听 ──────────────────────────────────────────────────────────────
HOST = _os.environ.get("MONPANEL_HOST", "0.0.0.0")
PORT = 8443
