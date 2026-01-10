import os
import sys
import uuid as uuidlib
from collections import defaultdict
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras


def get_db_url():
    url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
    if not url:
        # tentar carregar de .env em locais padrão
        candidates = [
            os.path.join(os.path.dirname(__file__), '..', '.env'),
            os.path.join(os.path.dirname(__file__), '..', '..', '.env'),
            os.path.join(os.getcwd(), '.env'),
        ]
        for p in candidates:
            try:
                p = os.path.abspath(p)
                if os.path.exists(p):
                    with open(p, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith('#'):
                                continue
                            if line.startswith('DATABASE_URL='):
                                url = line.split('=', 1)[1].strip().strip('"').strip("'")
                                break
                            if line.startswith('DATABASE_PUBLIC_URL='):
                                url = line.split('=', 1)[1].strip().strip('"').strip("'")
                                break
                if url:
                    break
            except Exception:
                pass
    if not url:
        print("❌ Nenhuma variável de conexão encontrada no ambiente nem em .env")
        print("   - Defina DATABASE_PUBLIC_URL ou DATABASE_URL")
        sys.exit(1)
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        print("🔄 Convertendo URL de asyncpg para psycopg2")
    return url


def fetch_vendas_and_itens(conn):
    sql = """
    SELECT 
      v.id::text as venda_id,
      v.usuario_id::text as usuario_id,
      v.total,
      v.desconto,
      v.forma_pagamento,
      v.created_at,
      v.cancelada,
      i.produto_id::text as produto_id,
      i.quantidade,
      i.peso_kg,
      i.preco_unitario,
      i.subtotal
    FROM vendas v
    LEFT JOIN itens_venda i ON i.venda_id = v.id
    WHERE v.cancelada = false
    ORDER BY v.created_at ASC
    """
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    # build map
    vendas = {}
    for r in rows:
        vid = r["venda_id"]
        if vid not in vendas:
            vendas[vid] = {
                "id": vid,
                "usuario_id": r["usuario_id"],
                "total": float(r["total"] or 0),
                "desconto": float(r["desconto"] or 0),
                "forma_pagamento": r["forma_pagamento"],
                "created_at": r["created_at"],
                "itens": []
            }
        if r["produto_id"]:
            vendas[vid]["itens"].append({
                "produto_id": r["produto_id"],
                "quantidade": int(r["quantidade"] or 0),
                "peso_kg": float(r["peso_kg"] or 0),
                "preco_unitario": float(r["preco_unitario"] or 0),
                "subtotal": float(r["subtotal"] or 0),
            })
    return list(vendas.values())


def build_signature(v):
    # assinatura baseada em total, forma_pagamento e lista ordenada de itens (produto_id, qtd/peso, subtotal)
    total = round(float(v.get("total") or 0), 6)
    forma = str(v.get("forma_pagamento") or "")
    itens = v.get("itens") or []
    key_items = []
    for it in itens:
        key_items.append((
            str(it.get("produto_id") or ""),
            int(it.get("quantidade") or 0),
            round(float(it.get("peso_kg") or 0), 6),
            round(float(it.get("preco_unitario") or 0), 6),
            round(float(it.get("subtotal") or 0), 6),
        ))
    key_items.sort()
    return (total, forma, tuple(key_items))


def choose_to_keep(group):
    # preferir com usuario_id != null; se empatar, o mais antigo (created_at menor)
    def rank(v):
        return (0 if v.get("usuario_id") else 1, v.get("created_at") or datetime.now(timezone.utc))
    return sorted(group, key=rank)[0]


def delete_venda(conn, venda_id):
    with conn.cursor() as cur:
        # deletar itens primeiro
        cur.execute("DELETE FROM itens_venda WHERE venda_id = %s", (venda_id,))
        # deletar venda
        cur.execute("DELETE FROM vendas WHERE id = %s", (venda_id,))


def main():
    url = get_db_url()
    conn = psycopg2.connect(url)
    try:
        vendas = fetch_vendas_and_itens(conn)
        groups = defaultdict(list)
        for v in vendas:
            sig = build_signature(v)
            groups[sig].append(v)

        # localizar grupos com duplicatas (mesma assinatura, mais de 1)
        dups = {sig: lst for sig, lst in groups.items() if len(lst) > 1}
        if not dups:
            print("✅ Nenhuma venda duplicada encontrada pela assinatura")
            return

        total_removed = 0
        print(f"🔎 Encontrados {len(dups)} grupos com possíveis duplicatas")
        for sig, lst in dups.items():
            keep = choose_to_keep(lst)
            to_remove = [v for v in lst if v["id"] != keep["id"]]
            if not to_remove:
                continue
            print("\nAssinatura:", sig)
            print("Manter:", keep["id"], keep["usuario_id"], keep["total"], keep["created_at"])
            print("Remover:", [v["id"] for v in to_remove])
            # aplicar remoção
            for v in to_remove:
                delete_venda(conn, v["id"])
                total_removed += 1
        conn.commit()
        print(f"\n🧹 Limpeza concluída. Vendas removidas: {total_removed}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
