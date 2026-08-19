from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig


def migrate() -> None:
    alembic_config = AlembicConfig(
        str(Path(__file__).resolve().parent.parent / "alembic.ini")
    )
    command.upgrade(alembic_config, "head")
