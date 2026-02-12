from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional, List
from datetime import date
import uuid

from app.db.database import get_db_session
from app.db.models import DespesaRecorrente, CategoriaDespesa

router = APIRouter(prefix="/api/despesas", tags=["Despesas"])


def _parse_date(value: Optional[str], field: str) -> Optional[date]:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} inválida")


def _serialize_despesa(d: DespesaRecorrente) -> dict:
    return {
        "id": str(d.id),
        "tipo": d.tipo,
        "categoria": d.categoria,
        "descricao": d.descricao,
        "valor": float(d.valor or 0),
        "status": d.status,
        "data_pagamento": d.data_pagamento.isoformat() if d.data_pagamento else None,
        "data_vencimento": d.data_vencimento.isoformat() if d.data_vencimento else None,
        "usuario_id": str(d.usuario_id) if d.usuario_id else None,
        "fechada": bool(d.fechada),
        "created_at": d.created_at.isoformat() if getattr(d, "created_at", None) else None,
        "updated_at": d.updated_at.isoformat() if getattr(d, "updated_at", None) else None,
    }


@router.get("/categorias")
async def listar_categorias(db: AsyncSession = Depends(get_db_session)):
    res = await db.execute(select(CategoriaDespesa).order_by(CategoriaDespesa.nome.asc()))
    rows: List[CategoriaDespesa] = res.scalars().all()
    return [{"id": str(r.id), "nome": r.nome} for r in rows]


@router.post("/categorias")
async def criar_categoria(payload: dict, db: AsyncSession = Depends(get_db_session)):
    nome = (payload.get("nome") or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="nome é obrigatório")

    res = await db.execute(select(CategoriaDespesa).where(func.lower(CategoriaDespesa.nome) == func.lower(nome)))
    existing = res.scalar_one_or_none()
    if existing:
        return {"id": str(existing.id), "nome": existing.nome}

    obj = CategoriaDespesa(nome=nome)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return {"id": str(obj.id), "nome": obj.nome}


@router.get("/")
async def listar_despesas(
    fechada: int = Query(0, description="0=aberta, 1=fechada"),
    categoria: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    data_inicio: Optional[str] = Query(None, description="YYYY-MM-DD"),
    data_fim: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db_session),
):
    di = _parse_date(data_inicio, "data_inicio")
    df = _parse_date(data_fim, "data_fim")

    q = select(DespesaRecorrente)
    q = q.where(DespesaRecorrente.fechada == (fechada == 1))

    if categoria:
        q = q.where(DespesaRecorrente.categoria == categoria)
    if tipo:
        q = q.where(DespesaRecorrente.tipo == tipo)
    if di:
        q = q.where(DespesaRecorrente.data_pagamento >= di)
    if df:
        q = q.where(DespesaRecorrente.data_pagamento <= df)

    q = q.order_by(desc(DespesaRecorrente.created_at))

    res = await db.execute(q)
    rows: List[DespesaRecorrente] = res.scalars().all()
    return [_serialize_despesa(r) for r in rows]


@router.get("/total")
async def total_despesas(
    fechada: int = Query(0, description="0=aberta, 1=fechada"),
    db: AsyncSession = Depends(get_db_session),
):
    res = await db.execute(
        select(func.coalesce(func.sum(DespesaRecorrente.valor), 0.0))
        .where(DespesaRecorrente.fechada == (fechada == 1))
    )
    total = res.scalar_one() or 0.0
    return {"total": float(total)}


@router.get("/historico")
async def historico_despesas(
    limit: int = Query(300, ge=1, le=2000),
    db: AsyncSession = Depends(get_db_session),
):
    res = await db.execute(
        select(DespesaRecorrente)
        .order_by(desc(DespesaRecorrente.created_at))
        .limit(limit)
    )
    rows: List[DespesaRecorrente] = res.scalars().all()
    return [_serialize_despesa(r) for r in rows]


@router.post("/")
async def criar_despesa(payload: dict, db: AsyncSession = Depends(get_db_session)):
    tipo = (payload.get("tipo") or "").strip()
    categoria = (payload.get("categoria") or "").strip()
    descricao = (payload.get("descricao") or "").strip()
    valor = payload.get("valor")

    if not tipo:
        raise HTTPException(status_code=400, detail="tipo é obrigatório")
    if not categoria:
        raise HTTPException(status_code=400, detail="categoria é obrigatório")
    if not descricao:
        raise HTTPException(status_code=400, detail="descricao é obrigatório")

    try:
        valor_f = float(valor)
    except Exception:
        raise HTTPException(status_code=400, detail="valor inválido")

    data_pagamento = _parse_date(payload.get("data_pagamento"), "data_pagamento")
    data_vencimento = _parse_date(payload.get("data_vencimento"), "data_vencimento")

    today = date.today()
    if data_pagamento is None:
        data_pagamento = today
    if data_vencimento is None:
        data_vencimento = data_pagamento

    usuario_id_raw = payload.get("usuario_id")
    usuario_uuid = None
    if usuario_id_raw:
        try:
            usuario_uuid = uuid.UUID(str(usuario_id_raw))
        except Exception:
            usuario_uuid = None

    obj = DespesaRecorrente(
        tipo=tipo,
        categoria=categoria,
        descricao=descricao,
        valor=valor_f,
        status=(payload.get("status") or "Pago"),
        data_pagamento=data_pagamento,
        data_vencimento=data_vencimento,
        usuario_id=usuario_uuid,
        fechada=bool(payload.get("fechada") or False),
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return _serialize_despesa(obj)


@router.put("/{despesa_id}")
async def atualizar_despesa(despesa_id: str, payload: dict, db: AsyncSession = Depends(get_db_session)):
    try:
        did = uuid.UUID(despesa_id)
    except Exception:
        raise HTTPException(status_code=400, detail="id inválido")

    res = await db.execute(select(DespesaRecorrente).where(DespesaRecorrente.id == did))
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")

    if "tipo" in payload and payload["tipo"] is not None:
        obj.tipo = str(payload["tipo"]).strip()
    if "categoria" in payload and payload["categoria"] is not None:
        obj.categoria = str(payload["categoria"]).strip()
    if "descricao" in payload and payload["descricao"] is not None:
        obj.descricao = str(payload["descricao"]).strip()
    if "valor" in payload and payload["valor"] is not None:
        try:
            obj.valor = float(payload["valor"])
        except Exception:
            raise HTTPException(status_code=400, detail="valor inválido")
    if "status" in payload and payload["status"] is not None:
        obj.status = str(payload["status"]).strip()
    if "data_pagamento" in payload:
        obj.data_pagamento = _parse_date(payload.get("data_pagamento"), "data_pagamento")
    if "data_vencimento" in payload:
        obj.data_vencimento = _parse_date(payload.get("data_vencimento"), "data_vencimento")
    if "fechada" in payload:
        obj.fechada = bool(payload.get("fechada"))

    await db.commit()
    await db.refresh(obj)
    return _serialize_despesa(obj)


@router.delete("/{despesa_id}")
async def excluir_despesa(despesa_id: str, db: AsyncSession = Depends(get_db_session)):
    try:
        did = uuid.UUID(despesa_id)
    except Exception:
        raise HTTPException(status_code=400, detail="id inválido")

    res = await db.execute(select(DespesaRecorrente).where(DespesaRecorrente.id == did))
    obj = res.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")

    await db.delete(obj)
    await db.commit()
    return {"ok": True}
