"""Read database connectivity and the Alembic revision without hiding failures."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.app.core.config import repo_root

logger = logging.getLogger(__name__)


def alembic_head() -> str | None:
    """Return the current Alembic head, or null when no migration scripts exist."""

    versions = repo_root() / "backend" / "alembic" / "versions"
    config_path = repo_root() / "backend" / "alembic.ini"
    if not config_path.is_file() or not versions.is_dir():
        return None
    if not any(versions.glob("*.py")):
        return None
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(config_path))
    script = ScriptDirectory.from_config(config)
    return script.get_current_head()


def database_status(engine: Engine, head: str | None) -> dict[str, Any]:
    """Connect and read ``alembic_version``. Reasons stay generic so paths are not returned."""

    try:
        with engine.connect() as connection:
            try:
                rows = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).fetchall()
            except Exception:
                logger.info("alembic_version is not readable", exc_info=True)
                return {
                    "connected": True,
                    "revision": None,
                    "head": head,
                    "reason": "The database is reachable but has no alembic_version table.",
                }
    except Exception:
        logger.info("database connection failed", exc_info=True)
        return {
            "connected": False,
            "revision": None,
            "head": head,
            "reason": "The database connection failed.",
        }

    if not rows:
        return {
            "connected": True,
            "revision": None,
            "head": head,
            "reason": "alembic_version has no revision row.",
        }
    revisions = [str(row[0]) for row in rows]
    if len(revisions) > 1:
        return {
            "connected": True,
            "revision": ",".join(revisions),
            "head": head,
            "reason": "The database has more than one alembic revision row.",
        }
    revision = revisions[0]
    reason = None
    if head is not None and revision != head:
        reason = "The applied migration revision does not match the migration head."
    return {"connected": True, "revision": revision, "head": head, "reason": reason}


def storage_status(path: Path) -> dict[str, Any]:
    """Write and remove a probe file. The response does not include the path."""

    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".beai_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        logger.info("storage directory is not writable", exc_info=True)
        return {"writable": False, "reason": "The storage directory is not writable."}
    return {"writable": True, "reason": None}
