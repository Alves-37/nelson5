#!/usr/bin/env python3
"""
Script para executar migração de IVA:
- Adiciona colunas taxa_iva / codigo_imposto em produtos
- Adiciona colunas taxa_iva / base_iva / valor_iva em itens_venda

Uso:
  python backend/scripts/run_migration_iva.py

Pré-requisitos:
  - DATABASE_URL configurada (no .env ou variável de ambiente)
  - Dependências do backend instaladas (sqlalchemy[asyncio], asyncpg, python-dotenv se quiser carregar .env)
"""
import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Garantir que o root do projeto esteja no sys.path para reaproveitar config, se necessário
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Caminho do arquivo SQL
SQL_FILE = Path(__file__).with_name("add_iva_columns.sql")


async def run():
    if not SQL_FILE.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {SQL_FILE}")

    # Tentar usar o mesmo esquema de URL do backend
    db_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL") or ""
    if not db_url:
        # fallback: tentar SETTINGS do app, se disponível
        try:
            from app.core.config import settings  # type: ignore
            db_url = settings.DATABASE_URL
        except Exception:
            db_url = ""

    if not db_url:
        raise RuntimeError("DATABASE_URL não definida e nenhum fallback configurado")

    # Garantir formato asyncpg
    if not db_url.startswith("postgresql+asyncpg://"):
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print("\n=== MIGRATION: adicionar colunas de IVA em produtos e itens_venda ===")
    print(f"DB URL: {db_url}")

    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    try:
        sql = SQL_FILE.read_text(encoding="utf-8")
        statements = [s.strip() for s in sql.split(";") if s.strip()]

        async with engine.begin() as conn:
            for stmt in statements:
                print(f"-> Executando: {stmt[:80]}...")
                await conn.execute(text(stmt))
        print("✅ Migração de IVA concluída com sucesso.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
