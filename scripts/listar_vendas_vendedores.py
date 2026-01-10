#!/usr/bin/env python3
"""
Script para listar vendas com seus respectivos vendedores

Uso:
  python backend/scripts/listar_vendas_vendedores.py

Opções:
  --limit N        Limitar número de vendas (padrão: 50)
  --data-inicio    Filtrar a partir de data (YYYY-MM-DD)
  --data-fim       Filtrar até data (YYYY-MM-DD)
  --usuario-id     Filtrar por ID específico do usuário
  --formato        Formato de saída: table, csv, json (padrão: table)

Exemplos:
  python backend/scripts/listar_vendas_vendedores.py --limit 20
  python backend/scripts/listar_vendas_vendedores.py --data-inicio 2025-01-01 --formato csv
  python backend/scripts/listar_vendas_vendedores.py --usuario-id abc123 --formato json
"""
import os
import sys
import argparse
import json
import csv
from datetime import datetime
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ Nenhuma variável de conexão encontrada (.env/ambiente)")
    print("   - Defina DATABASE_PUBLIC_URL ou DATABASE_URL")
    sys.exit(1)

# Converter URL asyncpg para psycopg2 se necessário
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

def format_currency(value):
    """Formatar valor como moeda MT."""
    if value is None:
        return "MT 0.00"
    return f"MT {float(value):.2f}"

def format_datetime(dt):
    """Formatar datetime para string legível."""
    if dt is None:
        return "N/A"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def get_vendas_vendedores(limit=50, data_inicio=None, data_fim=None, usuario_id=None):
    """Buscar vendas com informações dos vendedores."""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        
        with conn.cursor() as cursor:
            # Query base
            query = """
                SELECT 
                    v.id,
                    v.created_at as data_venda,
                    v.total,
                    v.desconto,
                    v.forma_pagamento,
                    v.cancelada,
                    v.usuario_id,
                    u.nome as vendedor_nome,
                    u.usuario as vendedor_login,
                    u.is_admin as vendedor_admin,
                    COUNT(iv.id) as total_itens,
                    STRING_AGG(
                        p.nome || ' (x' || iv.quantidade || ')', 
                        ', ' ORDER BY p.nome
                    ) as itens_resumo
                FROM vendas v
                LEFT JOIN usuarios u ON v.usuario_id = u.id
                LEFT JOIN itens_venda iv ON v.id = iv.venda_id
                LEFT JOIN produtos p ON iv.produto_id = p.id
                WHERE 1=1
            """
            
            params = []
            
            # Aplicar filtros
            if data_inicio:
                query += " AND DATE(v.created_at) >= %s"
                params.append(data_inicio)
                
            if data_fim:
                query += " AND DATE(v.created_at) <= %s"
                params.append(data_fim)
                
            if usuario_id:
                query += " AND v.usuario_id = %s"
                params.append(usuario_id)
            
            query += """
                GROUP BY v.id, v.created_at, v.total, v.desconto, v.forma_pagamento, 
                         v.cancelada, v.usuario_id, u.nome, u.usuario, u.is_admin
                ORDER BY v.created_at DESC
                LIMIT %s
            """
            params.append(limit)
            
            cursor.execute(query, params)
            vendas = cursor.fetchall()
            
        conn.close()
        return [dict(venda) for venda in vendas]
        
    except psycopg2.Error as e:
        print(f"❌ Erro de banco de dados: {e}")
        return []
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return []

def print_table(vendas):
    """Imprimir vendas em formato tabela."""
    if not vendas:
        print("📭 Nenhuma venda encontrada")
        return
    
    print(f"\n📊 {len(vendas)} vendas encontradas:")
    print("=" * 120)
    print(f"{'ID':<8} {'Data/Hora':<19} {'Total':<12} {'Vendedor':<20} {'Login':<15} {'Pagamento':<12} {'Status':<10}")
    print("-" * 120)
    
    total_geral = 0
    vendedores_stats = {}
    
    for venda in vendas:
        venda_id = str(venda['id'])[:8]
        data = format_datetime(venda['data_venda'])[:19]
        total = format_currency(venda['total'])
        vendedor = (venda['vendedor_nome'] or 'Sem vendedor')[:20]
        login = (venda['vendedor_login'] or 'N/A')[:15]
        pagamento = (venda['forma_pagamento'] or 'N/A')[:12]
        status = "Cancelada" if venda['cancelada'] else "Ativa"
        
        print(f"{venda_id:<8} {data:<19} {total:<12} {vendedor:<20} {login:<15} {pagamento:<12} {status:<10}")
        
        # Estatísticas
        if not venda['cancelada']:
            total_geral += float(venda['total'] or 0)
            
        vendedor_key = venda['vendedor_nome'] or 'Sem vendedor'
        if vendedor_key not in vendedores_stats:
            vendedores_stats[vendedor_key] = {'vendas': 0, 'total': 0}
        vendedores_stats[vendedor_key]['vendas'] += 1
        if not venda['cancelada']:
            vendedores_stats[vendedor_key]['total'] += float(venda['total'] or 0)
    
    print("-" * 120)
    print(f"💰 Total geral (vendas ativas): {format_currency(total_geral)}")
    
    print("\n👥 Estatísticas por vendedor:")
    print("-" * 60)
    for vendedor, stats in sorted(vendedores_stats.items()):
        print(f"{vendedor:<25} {stats['vendas']:>3} vendas - {format_currency(stats['total'])}")

def print_csv(vendas):
    """Imprimir vendas em formato CSV."""
    if not vendas:
        print("id,data_venda,total,vendedor_nome,vendedor_login,forma_pagamento,status,total_itens")
        return
    
    writer = csv.writer(sys.stdout)
    writer.writerow(['id', 'data_venda', 'total', 'vendedor_nome', 'vendedor_login', 'forma_pagamento', 'status', 'total_itens', 'itens_resumo'])
    
    for venda in vendas:
        writer.writerow([
            str(venda['id']),
            format_datetime(venda['data_venda']),
            venda['total'],
            venda['vendedor_nome'] or '',
            venda['vendedor_login'] or '',
            venda['forma_pagamento'] or '',
            'Cancelada' if venda['cancelada'] else 'Ativa',
            venda['total_itens'] or 0,
            venda['itens_resumo'] or ''
        ])

def print_json(vendas):
    """Imprimir vendas em formato JSON."""
    # Converter datetime para string para serialização JSON
    vendas_json = []
    for venda in vendas:
        venda_copy = dict(venda)
        venda_copy['data_venda'] = format_datetime(venda['data_venda'])
        venda_copy['id'] = str(venda_copy['id'])
        venda_copy['usuario_id'] = str(venda_copy['usuario_id']) if venda_copy['usuario_id'] else None
        vendas_json.append(venda_copy)
    
    print(json.dumps(vendas_json, indent=2, ensure_ascii=False))

def main():
    parser = argparse.ArgumentParser(description='Listar vendas com seus respectivos vendedores')
    parser.add_argument('--limit', type=int, default=50, help='Limitar número de vendas (padrão: 50)')
    parser.add_argument('--data-inicio', help='Filtrar a partir de data (YYYY-MM-DD)')
    parser.add_argument('--data-fim', help='Filtrar até data (YYYY-MM-DD)')
    parser.add_argument('--usuario-id', help='Filtrar por ID específico do usuário')
    parser.add_argument('--formato', choices=['table', 'csv', 'json'], default='table', 
                       help='Formato de saída (padrão: table)')
    
    args = parser.parse_args()
    
    if args.formato == 'table':
        print("🚀 Listando vendas com vendedores...")
        if args.data_inicio or args.data_fim:
            periodo = f" (período: {args.data_inicio or 'início'} até {args.data_fim or 'hoje'})"
            print(f"📅 Filtros aplicados{periodo}")
        if args.usuario_id:
            print(f"👤 Filtro por usuário: {args.usuario_id}")
    
    vendas = get_vendas_vendedores(
        limit=args.limit,
        data_inicio=args.data_inicio,
        data_fim=args.data_fim,
        usuario_id=args.usuario_id
    )
    
    if args.formato == 'table':
        print_table(vendas)
    elif args.formato == 'csv':
        print_csv(vendas)
    elif args.formato == 'json':
        print_json(vendas)

if __name__ == "__main__":
    main()
