import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"), # "db" is the service name in docker-compose
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT", "5432")
    )


def save_pair_to_db(user_id: str, instrument_id: str, experiment_name: str, metadata_path: str, data_path: str, cell_id: str = None):
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        INSERT INTO file_pairs (user_id, instrument_id, experiment_name, metadata_path, data_path, cell_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING pair_id;
    """
    
    try:
        cur.execute(query, (user_id, instrument_id, experiment_name, metadata_path, data_path, cell_id))
        pair_id = cur.fetchone()[0]
        conn.commit()
        return pair_id
    except Exception as e:
        conn.rollback()  # Rollback changes if anything crashes (e.g., invalid user_id UUID)
        raise e
    finally:
        cur.close()
        conn.close()

def get_or_create_instrument(model_name: str):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Check if it already exists
        cur.execute("SELECT instrument_id FROM instruments WHERE model_name = %s;", (model_name,))
        row = cur.fetchone()
        
        if row:
            return row[0]  # Return early if found
            
        # 2. Insert if it doesn't exist
        query = """
            INSERT INTO instruments (model_name)
            VALUES (%s)
            ON CONFLICT (model_name) DO NOTHING
            RETURNING instrument_id;
        """
        cur.execute(query, (model_name,))
        result = cur.fetchone()
        
        # Concurrency fallback if another thread inserted it at the same time
        if not result:
            cur.execute("SELECT instrument_id FROM instruments WHERE model_name = %s;", (model_name,))
            result = cur.fetchone()
            
        conn.commit()
        return result[0]
        
    except Exception as e:
        conn.rollback()  # Roll back changes safely if it crashes
        raise e
        
    finally:
        # This ALWAYS runs, ensuring we don't leak database connections
        cur.close()
        conn.close()

def get_or_create_cell(model_name: str):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Check if it already exists
        cur.execute("SELECT instrument_id FROM instruments WHERE model_name = %s;", (model_name,))
        row = cur.fetchone()
        
        if row:
            return row[0]  # Return early if found
            
        # 2. Insert if it doesn't exist
        query = """
            INSERT INTO cells (model_name)
            VALUES (%s)
            ON CONFLICT (model_name) DO NOTHING
            RETURNING cell_id;
        """
        cur.execute(query, (model_name,))
        result = cur.fetchone()
        
        # Concurrency fallback if another thread inserted it at the same time
        if not result:
            cur.execute("SELECT cell_id FROM cells WHERE model_name = %s;", (model_name,))
            result = cur.fetchone()
            
        conn.commit()
        return result[0]
        
    except Exception as e:
        conn.rollback()  # Roll back changes safely if it crashes
        raise e
        
    finally:
        # This ALWAYS runs, ensuring we don't leak database connections
        cur.close()
        conn.close()

def get_tests_by_instrument(model_name: str):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # We use an INNER JOIN to fetch the data along with the instrument info
    query = """
        SELECT fp.pair_id, fp.experiment_name, fp.metadata_path, fp.data_path, fp.created_at, i.model_name
        FROM file_pairs fp
        JOIN instruments i ON fp.instrument_id = i.instrument_id
        WHERE i.model_name = %s
        ORDER BY fp.created_at DESC;
    """
    try:
        cur.execute(query, (model_name,))
        columns = [desc[0] for desc in cur.description]
        # Convert rows into a list of dictionaries so FastAPI can easily serve it as clean JSON
        results = [dict(zip(columns, row)) for row in cur.fetchall()]
        return results
    finally:
        cur.close()
        conn.close()

def get_tests_by_user(username: str):
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT fp.pair_id, fp.experiment_name, fp.metadata_path, fp.data_path, fp.created_at, u.username
        FROM file_pairs fp
        JOIN users u ON fp.user_id = u.user_id
        WHERE u.username = %s
        ORDER BY fp.created_at DESC;
    """
    try:
        cur.execute(query, (username,))
        columns = [desc[0] for desc in cur.description]
        results = [dict(zip(columns, row)) for row in cur.fetchall()]
        return results
    finally:
        cur.close()
        conn.close()