import asyncio
import argparse
import os
import sys
import uuid
from sqlalchemy.future import select

# Ensure project root is on sys.path so 'app' can be imported when running this script directly
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.db.session import AsyncSessionLocal, engine
from app.db.base import DeclarativeBase
from app.db.models import Produto


DEFAULT_UUID = "157c293f-5995-4a83-9d2a-e02f811dd5f4"
DEFAULT_CODIGO = "SERVICO_IMPRESSAO"
DEFAULT_NOME = "Serviço de Impressão"
DEFAULT_DESCRICAO = "Serviço de impressão e cópias"


async def ensure_tables():
    async with engine.begin() as conn:
        await conn.run_sync(DeclarativeBase.metadata.create_all)


async def seed_servico_impressao(
    produto_uuid: str = DEFAULT_UUID,
    codigo: str = DEFAULT_CODIGO,
    nome: str = DEFAULT_NOME,
    descricao: str = DEFAULT_DESCRICAO,
):
    await ensure_tables()

    pid = uuid.UUID(produto_uuid)

    async with AsyncSessionLocal() as session:
        # 1) Check by UUID
        res = await session.execute(select(Produto).where(Produto.id == pid))
        prod = res.scalar_one_or_none()
        if prod:
            print(f"OK: Produto já existe por UUID: id={prod.id} codigo={prod.codigo} nome={prod.nome}")
            return

        # 2) Check by codigo (unique)
        if codigo:
            res2 = await session.execute(select(Produto).where(Produto.codigo == codigo))
            prod2 = res2.scalar_one_or_none()
            if prod2:
                # If codigo exists with different UUID, warn and do nothing (avoid breaking references)
                print(
                    "ATENÇÃO: Já existe um produto com codigo='{}' mas UUID diferente. "
                    "Existente id={} nome={}. Não foi criado novo produto.".format(codigo, prod2.id, prod2.nome)
                )
                return

        # 3) Create
        novo = Produto(
            id=pid,
            codigo=codigo,
            nome=nome,
            descricao=descricao,
            preco_custo=0.0,
            preco_venda=0.0,
            estoque=0.0,
            estoque_minimo=0.0,
            categoria_id=None,
            venda_por_peso=False,
            unidade_medida="serv",
            taxa_iva=0.0,
            ativo=True,
        )
        session.add(novo)
        await session.commit()
        await session.refresh(novo)
        print(f"CREATED: Produto SERVICO_IMPRESSAO criado: id={novo.id} codigo={novo.codigo} nome={novo.nome}")


def parse_args():
    parser = argparse.ArgumentParser(description="Seed do produto SERVICO_IMPRESSAO (uuid fixo para sync do PDV3)")
    parser.add_argument("--uuid", default=DEFAULT_UUID, help="UUID do produto (default: o UUID esperado pelo PDV3)")
    parser.add_argument("--codigo", default=DEFAULT_CODIGO, help="Código do produto")
    parser.add_argument("--nome", default=DEFAULT_NOME, help="Nome do produto")
    parser.add_argument("--descricao", default=DEFAULT_DESCRICAO, help="Descrição do produto")
    return parser.parse_args()


async def amain():
    args = parse_args()
    await seed_servico_impressao(
        produto_uuid=args.uuid,
        codigo=args.codigo,
        nome=args.nome,
        descricao=args.descricao,
    )


if __name__ == "__main__":
    asyncio.run(amain())
