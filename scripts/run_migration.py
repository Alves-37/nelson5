#!/usr/bin/env python3
"""
Run DB migration to align 'usuarios' table permissions with client PDV3 fields.
- Reads and executes scripts/migrate_permissions.sql against DATABASE_URL
- Uses SQLAlchemy async engine (asyncpg)

Usage:
  python scripts/run_migration.py
"""
import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Ensure project root is on sys.path so 'app' package can be imported when run from scripts/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load settings from app.core.config (keeps parity with app). Fallback to env var.
try:
    from app.core.config import settings  # type: ignore
    SETTINGS_OK = True
except Exception:
    settings = None
    SETTINGS_OK = False

SQL_FILE = Path(__file__).with_name("add_peso_kg_column.sql")


async def run():
    if not SQL_FILE.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {SQL_FILE}")

    # Ensure async URL (settings already tries to coerce to asyncpg). Fallback to env.
    if SETTINGS_OK and getattr(settings, 'DATABASE_URL', None):
        db_url = settings.DATABASE_URL
    else:
        db_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL", "")
        if not db_url:
            raise RuntimeError("DATABASE_URL não definido e não foi possível importar app.core.config.settings")
    if not db_url.startswith("postgresql+asyncpg://"):
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    print("\n=== MIGRATION: add peso_kg column ===")
    print(f"DB URL: {db_url}")

    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    try:
        sql = SQL_FILE.read_text(encoding="utf-8")
        # Split on semicolons to avoid multi-statement issues
        statements = [s.strip() for s in sql.split(";") if s.strip()]

        async with engine.begin() as conn:
            for stmt in statements:
                print(f"-> Executando: {stmt[:80]}...")
                await conn.execute(text(stmt))
        print("OK: Migração concluída com sucesso.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
