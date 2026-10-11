"""Apply Alembic migrations to a database URL."""

from alembic.config import Config

from alembic import command
from backend.app.core.config import repo_root


def upgrade_to_head(database_url: str) -> None:
    config_path = repo_root() / "backend" / "alembic.ini"
    config = Config(str(config_path))
    config.set_main_option("script_location", str(repo_root() / "backend" / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
