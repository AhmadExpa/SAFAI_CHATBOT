import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()  # Make sure this is called before os.getenv

print("DATABASE_URL:", os.getenv("DATABASE_URL"))  # Debug

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

# Run migrations in order
migration_files = [
    "001_create_users.sql",
    "002_create_projects.sql", 
    "003_create_conversations.sql",
    "004_create_bubbles.sql",
    "005_create_messages.sql",
    "006_add_conversation_constraints.sql",
    "007_create_project_files.sql",
    "008_create_password_reset_tokens.sql",
    "009_create_model_responses_and_comments.sql",
    "010_make_message_id_nullable.sql",
    "011_create_personalities.sql",
    "012_create_workspaces.sql"
]

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

for migration_file in migration_files:
    migration_path = os.path.join(script_dir, migration_file)
    print(f"Running migration: {migration_file}")
    try:
        with open(migration_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        cur.execute(migration_sql)
        conn.commit()
        print(f"  ✅ Migration {migration_file} completed")
    except psycopg2.errors.DuplicateTable as e:
        print(f"  ⚠️  Warning: Table/index already exists, skipping...")
        conn.rollback()
    except psycopg2.errors.DuplicateObject as e:
        print(f"  ⚠️  Warning: Object already exists, skipping...")
        conn.rollback()
    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
            print(f"  ⚠️  Warning: Object already exists ({error_msg.split(':')[0] if ':' in error_msg else error_msg}), skipping...")
            conn.rollback()
        else:
            print(f"  ❌ Error in migration {migration_file}: {e}")
            conn.rollback()
            print(f"  Continuing with next migration...")

cur.close()
conn.close()

print("\n✅ All migrations processed!")