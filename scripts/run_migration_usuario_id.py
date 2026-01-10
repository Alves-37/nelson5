#!/usr/bin/env python3
"""
Script para executar migração: adicionar usuario_id à tabela vendas

Uso:
  python backend/scripts/run_migration_usuario_id.py

Pré-requisitos:
  - DATABASE_URL no .env ou variável de ambiente
  - psycopg2 instalado (pip install psycopg2-binary)
"""
import os
import sys
from pathlib import Path
import psycopg2
from psycopg2 import sql
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
    print("🔄 Convertendo URL de asyncpg para psycopg2")

# SQL da migração
MIGRATION_SQL = """
-- Verificar se a coluna já existe
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'vendas' AND column_name = 'usuario_id'
    ) THEN
        -- Adicionar coluna usuario_id à tabela vendas
        ALTER TABLE vendas ADD COLUMN usuario_id UUID;
        RAISE NOTICE 'Coluna usuario_id adicionada à tabela vendas';
        
        -- Adicionar foreign key constraint
        ALTER TABLE vendas ADD CONSTRAINT fk_vendas_usuario_id 
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id);
        RAISE NOTICE 'Foreign key constraint adicionada';
        
        -- Criar índice para melhor performance
        CREATE INDEX idx_vendas_usuario_id ON vendas(usuario_id);
        RAISE NOTICE 'Índice idx_vendas_usuario_id criado';
        
        -- Comentário explicativo
        COMMENT ON COLUMN vendas.usuario_id IS 'ID do usuário que realizou a venda';
        RAISE NOTICE 'Comentário adicionado à coluna usuario_id';
        
    ELSE
        RAISE NOTICE 'Coluna usuario_id já existe na tabela vendas - migração ignorada';
    END IF;
END $$;
"""

def run_migration():
    """Executa a migração no banco de dados."""
    try:
        print(f"🔗 Conectando ao banco: {DATABASE_URL[:50]}...")
        
        # Conectar ao banco
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        
        with conn.cursor() as cursor:
            print("📝 Executando migração...")
            cursor.execute(MIGRATION_SQL)
            
            # Verificar se a migração foi aplicada
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'vendas' AND column_name = 'usuario_id'
                )
            """)
            exists = cursor.fetchone()[0]
            
            if exists:
                print("✅ Migração executada com sucesso!")
                print("   - Coluna usuario_id adicionada à tabela vendas")
                print("   - Foreign key constraint criada")
                print("   - Índice criado para performance")
                
                # Verificar constraint
                cursor.execute("""
                    SELECT constraint_name FROM information_schema.table_constraints 
                    WHERE table_name = 'vendas' AND constraint_name = 'fk_vendas_usuario_id'
                """)
                constraint = cursor.fetchone()
                if constraint:
                    print("   - Constraint de foreign key confirmada")
                
                # Verificar índice
                cursor.execute("""
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename = 'vendas' AND indexname = 'idx_vendas_usuario_id'
                """)
                index = cursor.fetchone()
                if index:
                    print("   - Índice confirmado")
                    
            else:
                print("❌ Falha na migração - coluna não foi criada")
                return False
                
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Erro de banco de dados: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

def main():
    print("🚀 Iniciando migração: adicionar usuario_id à tabela vendas")
    print("=" * 60)
    
    success = run_migration()
    
    print("=" * 60)
    if success:
        print("✅ Migração concluída com sucesso!")
        print("\n📋 Próximos passos:")
        print("1. Reinicie o backend para aplicar as mudanças no modelo")
        print("2. Teste no PDV3: faça login como funcionário e realize uma venda")
        print("3. Verifique em 'Minhas Vendas' se aparece apenas as vendas do usuário")
    else:
        print("❌ Migração falhou - verifique os logs acima")
        sys.exit(1)

if __name__ == "__main__":
    main()
