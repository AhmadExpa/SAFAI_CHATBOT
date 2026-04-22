"""
Run personalities migration on Supabase database
Usage: python migrations/run_personalities_migration.py
"""

import os
import sys
import asyncio
import asyncpg
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

async def run_migration():
    """Run the personalities migration"""
    
    # Get database URL from environment
    database_url = os.getenv("ASYNC_DATABASE_URL")
    
    if not database_url:
        print("❌ ASYNC_DATABASE_URL not found in environment variables")
        return False
    
    # Convert asyncpg URL if needed
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    print("🔗 Connecting to Supabase database...")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        print("✅ Connected successfully")
        
        # Read migration file
        migration_file = os.path.join(
            os.path.dirname(__file__),
            "011_create_personalities.sql"
        )
        
        print(f"📄 Reading migration: {migration_file}")
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        print("🚀 Executing migration...")
        
        # Execute migration
        await conn.execute(migration_sql)
        
        print("✅ Migration completed successfully!")
        
        # Verify by counting personalities
        count = await conn.fetchval("SELECT COUNT(*) FROM personalities")
        print(f"📊 Created {count} default personalities")
        
        # Show created personalities
        personalities = await conn.fetch(
            "SELECT name, highlight, avatar_emoji FROM personalities ORDER BY display_order"
        )
        
        print("\n🎭 Available Personalities:")
        for p in personalities:
            print(f"   {p['avatar_emoji']} {p['name']}: {p['highlight']}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🎭 PhatagiAI - Personalities Migration")
    print("=" * 60)
    
    success = asyncio.run(run_migration())
    
    if success:
        print("\n✅ All done! Personalities feature is ready to use.")
    else:
        print("\n❌ Migration failed. Please check the error messages above.")
        sys.exit(1)

