"""Apply the versioned ProofLayer SQL migrations to the configured database."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine


ROOT = Path(__file__).resolve().parent


class MigrationSettings(BaseSettings):
    database_url: str = ""
    model_config = SettingsConfigDict(env_file="backend/.env", extra="ignore")


def migrate() -> None:
    settings = MigrationSettings()
    database_url = settings.database_url or os.getenv("POSTGRES_URL") or "sqlite:///./prooflayer.db"
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    try:
        applied = []
        for migration in sorted((ROOT / "migrations").glob("*.sql")):
            statements = [part.strip() for part in migration.read_text(encoding="utf-8").split(";") if part.strip()]
            with engine.begin() as connection:
                for statement in statements:
                    connection.exec_driver_sql(statement)
            applied.append(migration.stem)
        print(f"Applied migrations through {applied[-1] if applied else 'none'}.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    migrate()
