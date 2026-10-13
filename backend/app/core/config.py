"""Runtime settings. Validated at startup. Paths resolve from the repository root."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend import __version__


def repo_root() -> Path:
    """Return the repository root (parent of the ``backend`` package)."""

    return Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Process configuration loaded from the environment and an optional ``.env`` file."""

    model_config = SettingsConfigDict(
        env_prefix="BEAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///data/beai.sqlite"
    storage_dir: Path = Path("data/structures")
    max_upload_bytes: int = 50 * 1024 * 1024
    max_atom_count: int = 200_000
    max_sequence_length: int = 50_000
    cors_origins: str = "http://127.0.0.1:8732,http://localhost:8732"
    host: str = "127.0.0.1"
    port: int = 8731
    ca_break_threshold_angstrom: float = 4.5
    log_level: str = "INFO"
    app_version: str = Field(default=__version__)

    @field_validator("max_upload_bytes", "max_atom_count", "max_sequence_length")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value

    @field_validator("ca_break_threshold_angstrom")
    @classmethod
    def _positive_threshold(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value

    def cors_origin_list(self) -> list[str]:
        origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        if not origins:
            raise ValueError("BEAI_CORS_ORIGINS must list at least one origin")
        return origins

    def resolved_storage_dir(self) -> Path:
        path = self.storage_dir
        if not path.is_absolute():
            path = repo_root() / path
        return path.resolve()

    def resolved_database_url(self) -> str:
        return resolve_sqlite_url(self.database_url, repo_root())


def resolve_sqlite_url(url: str, root: Path) -> str:
    """Make a relative SQLite path absolute against ``root``. Leave other URLs unchanged."""

    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    raw = url[len(prefix) :]
    if raw == ":memory:" or raw.startswith("file:"):
        return url
    path = Path(raw)
    if not path.is_absolute():
        path = (root / path).resolve()
    return prefix + path.as_posix()
