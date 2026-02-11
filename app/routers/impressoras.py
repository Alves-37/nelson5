from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from ..db.database import get_db_session
from ..db.models import Impressora

router = APIRouter(prefix="/api/impressoras", tags=["impressoras"])


@router.get("/", response_model=List[dict])
async def listar_impressoras(db: AsyncSession = Depends(get_db_session)):
    """Lista impressoras cadastradas (para sincronização dos NeoPDVs)."""
    try:
        result = await db.execute(select(Impressora).order_by(Impressora.numero_serie))
        impressoras = result.scalars().all()
        out = []
        for i in impressoras:
            try:
                out.append(
                    {
                        "id": str(i.id) if isinstance(i.id, uuid.UUID) else str(i.id),
                        "numero_serie": i.numero_serie,
                        "marca": i.marca or "",
                        "modelo": i.modelo or "",
                        "ativa": bool(i.ativa),
                        "created_at": i.created_at.isoformat() if getattr(i, "created_at", None) else None,
                        "updated_at": i.updated_at.isoformat() if getattr(i, "updated_at", None) else None,
                    }
                )
            except Exception:
                continue
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar impressoras: {str(e)}")
