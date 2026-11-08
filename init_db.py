import os
import psycopg2
from dotenv import load_dotenv

# Load the variables from .env
load_dotenv()

def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432")
    )

def create_tables():
    commands = (
        """
        CREATE TABLE IF NOT EXISTS files (
            file_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            file_name TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            mime_type VARCHAR(100),
            size_bytes BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS file_metadata (
            metadata_id SERIAL PRIMARY KEY,
            file_id UUID REFERENCES files(file_id) ON DELETE CASCADE,
            meta_key TEXT NOT NULL,
            meta_value TEXT NOT NULL
        )
        """
    )
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Ensure the pgcrypto extension is available for gen_random_uuid()
        cur.execute("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";")
        
        for command in commands:
            cur.execute(command)
            
        cur.close()
        conn.commit()
        print("Database initialized successfully with tables!")
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_tables()