"""Apply the versioned ProofLayer SQL migrations to the configured database."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine


ROOT = Path(__file__).resolve().parent


class MigrationSettings(BaseSettings):
    database_url: str = "sqlite:///./prooflayer.db"
    model_config = SettingsConfigDict(env_file="backend/.env", extra="ignore")


def migrate() -> None:
    settings = MigrationSettings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    engine = create_engine(settings.database_url, connect_args=connect_args)
    try:
        migration = ROOT / "migrations" / "0001_initial.sql"
        statements = [part.strip() for part in migration.read_text(encoding="utf-8").split(";") if part.strip()]
        with engine.begin() as connection:
            for statement in statements:
                connection.exec_driver_sql(statement)
        print("Applied migrations through 0001_initial.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    migrate()
