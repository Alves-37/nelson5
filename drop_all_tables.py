"""
Script to drop all tables in PostgreSQL database for clean reset.
"""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

async def drop_all_tables():
    """Drop all tables in the PostgreSQL database."""
    database_url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_PUBLIC_URL/DATABASE_URL not found in environment variables")
        return
    
    # Convert SQLAlchemy URL format to asyncpg format
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    elif database_url.startswith("postgres+asyncpg://"):
        database_url = database_url.replace("postgres+asyncpg://", "postgresql://")
    
    try:
        # Connect to PostgreSQL
        conn = await asyncpg.connect(database_url)
        print("Connected to PostgreSQL database")
        
        # Get all table names
        tables_query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        """
        
        tables = await conn.fetch(tables_query)
        table_names = [table['table_name'] for table in tables]
        
        if not table_names:
            print("No tables found to drop")
            await conn.close()
            return
        
        print(f"Found {len(table_names)} tables to drop: {', '.join(table_names)}")
        
        # Drop all tables with CASCADE to handle foreign key constraints
        for table_name in table_names:
            drop_query = f"DROP TABLE IF EXISTS {table_name} CASCADE"
            await conn.execute(drop_query)
            print(f"Dropped table: {table_name}")
        
        # Verify all tables are dropped
        remaining_tables = await conn.fetch(tables_query)
        if remaining_tables:
            print(f"WARNING: {len(remaining_tables)} tables still exist")
        else:
            print("SUCCESS: All tables dropped successfully")
        
        await conn.close()
        print("Database connection closed")
        
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    asyncio.run(drop_all_tables())
