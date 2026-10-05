"""模型配置（Profiles）：多套 LLM 配置的 CRUD 持久化。

存 SQLite（~/.context-pilot/profiles.db），字段对齐 OpenAI 协议所需。
API Key 以 base64 简单脱敏存储（非加密；提示：生产应改用系统密钥环）。
对外暴露的 profile 对象中 api_key 始终脱敏，明文只在内部调用时提供。
"""

import base64
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_DEFAULT_DIR = Path.home() / ".context-pilot"
_DB_NAME = "profiles.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_profiles (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    provider    TEXT NOT NULL DEFAULT 'openai',
    base_url    TEXT NOT NULL,
    api_key     TEXT NOT NULL DEFAULT '',
    model       TEXT NOT NULL,
    temperature REAL NOT NULL DEFAULT 0.2,
    max_tokens  INTEGER NOT NULL DEFAULT 6000,
    enabled     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
)
"""


def _mask(key: str) -> str:
    """脱敏：只保留前缀 + 尾 4 字符，其余打码。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def _obfuscate(key: str) -> str:
    """简单混淆存储（防明文落盘）。非加密，生产建议改用密钥环。"""
    if not key:
        return ""
    return base64.b64encode(key.encode("utf-8")).decode("ascii")


def _deobfuscate(value: str) -> str:
    if not value:
        return ""
    try:
        return base64.b64decode(value.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return value


@dataclass(frozen=True)
class ModelProfile:
    """一套完整模型配置。api_key 字段对外始终为脱敏值。"""

    id: str = ""
    name: str = ""
    provider: str = "openai"
    base_url: str = ""
    api_key: str = ""  # 脱敏后的展示值
    model: str = ""
    temperature: float = 0.2
    max_tokens: int = 6000
    enabled: bool = False
    created_at: str = ""


class ProfileStore:
    """模型配置的 SQLite CRUD。"""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._path = (base_dir or _DEFAULT_DIR) / _DB_NAME
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(_SCHEMA)

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def list(self) -> "list[ModelProfile]":
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM model_profiles ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def list_enabled(self) -> "list[ModelProfile]":
        """启用的配置（按创建顺序）。调用方取第一个作为当前生效配置。"""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM model_profiles WHERE enabled = 1 ORDER BY created_at ASC"
            ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def get(self, profile_id: str) -> "ModelProfile | None":
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM model_profiles WHERE id = ?", (profile_id,)
            ).fetchone()
        return self._row_to_profile(row) if row else None

    def add(
        self,
        *,
        name: str,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        enabled: bool,
    ) -> "ModelProfile":
        # 必填校验
        missing = [
            k
            for k, v in {
                "name": name,
                "provider": provider,
                "base_url": base_url,
                "model": model,
            }.items()
            if not v.strip()
        ]
        if missing:
            raise ValueError(f"缺少必填字段：{', '.join(missing)}")

        profile_id = uuid.uuid4().hex[:12]
        now = self._now()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO model_profiles"
                " (id, name, provider, base_url, api_key, model, temperature,"
                "  max_tokens, enabled, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    profile_id,
                    name,
                    provider,
                    base_url,
                    _obfuscate(api_key),
                    model,
                    temperature,
                    max_tokens,
                    1 if enabled else 0,
                    now,
                ),
            )
        return self.get(profile_id)  # type: ignore[return-value]

    def update(self, profile_id: str, **fields) -> "ModelProfile | None":
        """更新非敏感字段；api_key 传明文则混淆存储。"""
        existing = self.get(profile_id)
        if existing is None:
            return None

        allowed = {
            "name",
            "provider",
            "base_url",
            "model",
            "temperature",
            "max_tokens",
            "enabled",
        }
        sets: list[str] = []
        values: list = []
        for key, value in fields.items():
            if key == "api_key" and value is not None:
                sets.append("api_key = ?")
                values.append(_obfuscate(str(value)))
            elif key in allowed:
                sets.append(f"{key} = ?")
                if key == "enabled":
                    values.append(1 if value else 0)
                else:
                    values.append(value)
        if not sets:
            return existing

        values.append(profile_id)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                f"UPDATE model_profiles SET {', '.join(sets)} WHERE id = ?", values
            )
        return self.get(profile_id)

    def delete(self, profile_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "DELETE FROM model_profiles WHERE id = ?", (profile_id,)
            )
        return cursor.rowcount > 0

    def set_enabled(self, profile_id: str, enabled: bool) -> None:
        """启用一个配置；若启用则先取消其他配置的启用（单一生效）。"""
        with closing(self._connect()) as conn, conn:
            if enabled:
                conn.execute("UPDATE model_profiles SET enabled = 0")
            conn.execute(
                "UPDATE model_profiles SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, profile_id),
            )

    def reveal_key_by_id(self, profile_id: str) -> str:
        """仅供 Provider 内部调用：按 id 取回明文 key。脱敏展示值无法还原。"""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT api_key FROM model_profiles WHERE id = ?", (profile_id,)
            ).fetchone()
        if row is None:
            return ""
        return _deobfuscate(row["api_key"])

    @staticmethod
    def _row_to_profile(row: sqlite3.Row) -> "ModelProfile":
        raw_key = row["api_key"]
        return ModelProfile(
            id=row["id"],
            name=row["name"],
            provider=row["provider"],
            base_url=row["base_url"],
            api_key=_mask(_deobfuscate(raw_key)),
            model=row["model"],
            temperature=row["temperature"],
            max_tokens=row["max_tokens"],
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
        )
