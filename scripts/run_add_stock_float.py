#!/usr/bin/env python3
"""
Runner para aplicar backend/scripts/add_stock_float.sql no banco PostgreSQL.

Uso:
  python backend/scripts/run_add_stock_float.py

Requisitos:
  - DATABASE_URL definido (ou disponível em app.core.config.settings)
  - Acesso ao banco
"""
import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Tentar carregar settings do app (opcional)
try:
    from app.core.config import settings  # type: ignore
    SETTINGS_OK = True
except Exception:
    settings = None
    SETTINGS_OK = False

SQL_FILE = Path(__file__).with_name("add_stock_float.sql")

async def run():
    if not SQL_FILE.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {SQL_FILE}")

    # Resolver URL do banco
    if SETTINGS_OK and getattr(settings, 'DATABASE_URL', None):
        db_url = settings.DATABASE_URL
    else:
        db_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL", "")
        if not db_url:
            raise RuntimeError("DATABASE_URL não definido e não foi possível importar app.core.config.settings")

    # Garantir asyncpg
    if not db_url.startswith("postgresql+asyncpg://"):
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    print("\n=== MIGRATION: add_stock_float.sql ===")
    print(f"DB URL: {db_url}")

    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    try:
        sql = SQL_FILE.read_text(encoding="utf-8")
        # Simples split por ';' (ignorando vazios)
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        async with engine.begin() as conn:
            for stmt in statements:
                # Mostrar só o início do comando para log
                print(f"-> Executando: {stmt[:120]}...")
                await conn.execute(text(stmt))
        print("OK: Migração concluída com sucesso.")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run())
