import datetime
import re

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from app.database import (
    get_or_create_instrument, 
    save_pair_to_db, 
    get_tests_by_instrument, 
    get_tests_by_user,
    get_or_create_cell
)
from fastapi.responses import FileResponse
import os
import shutil
from uuid import uuid4
import json
from app.database import get_db_connection
import time
from contextlib import asynccontextmanager


UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")  # Default to "uploads" if not set

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Try up to 5 times to connect and seed the user
    for attempt in range(5):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Ensure table exists just in case init.sql is completely skipped
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id UUID PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL
                );
            """)
            
            # Seed our test user
            cur.execute("""
                INSERT INTO users (user_id, username)
                VALUES ('11111111-1111-1111-1111-111111111111', 'alice')
                ON CONFLICT (user_id) DO NOTHING;
            """)
            
            conn.commit()
            cur.close()
            conn.close()
            print("🚀 Database successfully synchronized and seeded with 'alice'!")
            break # Success! Break out of the retry loop.
        except Exception as e:
            print(f"⏳ Postgres isn't ready yet (attempt {attempt + 1}/5)... waiting 2 seconds.")
            time.sleep(2)
    else:
        print("❌ Critical: Could not connect to database after 5 attempts.")
        
    yield

app = FastAPI(lifespan=lifespan)


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


@app.post("/upload-pair")
async def upload_file_pair(
    metadata_file: UploadFile = File(...), 
    data_file: UploadFile = File(...)
):
    # 1. Read and parse metadata json
    metadata_content = await metadata_file.read()
    metadata_json = json.loads(metadata_content)
    
    user_id = metadata_json.get("user_id")
    experiment_name = metadata_json.get("experiment_name", "Untitled")
    
    meta_user = metadata_json.get("username", "").strip()
    meta_inst = metadata_json.get("instrument_name", "").strip()
    meta_date = metadata_json.get("date", "").strip()

    # 2. Strict text validation (Allows letters, numbers, hyphens, and underscores)
    ALLOWED_PATTERN = r"^[a-zA-Z0-9_-]+$"
    if not re.match(ALLOWED_PATTERN, meta_user) or not re.match(ALLOWED_PATTERN, meta_inst):
        raise HTTPException(status_code=400, detail="Invalid characters in username or instrument")

    if meta_inst:
        # If the json contains an instrument name, dynamically look it up or provision it!
        instrument_id = get_or_create_instrument(meta_inst)

    cell_name = metadata_json.get("cell_name")
    cell_id = None

    if cell_name:
        cell_id = get_or_create_cell(cell_name)

    # 3. Parse full high-precision timestamp
    try:
        # Handle standard ISO formats (e.g., 2026-07-11T09:35:49Z)
        clean_timestamp = meta_date.replace("Z", "+00:00").replace(" ", "T")
        parsed_dt = datetime.fromisoformat(clean_timestamp)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail="Timestamp must include full time details (e.g., YYYY-MM-DDTHH:MM:SSZ)"
        )

    # 4. Partition our path values
    date_folder = parsed_dt.date().isoformat()       # e.g., "2026-07-11"
    time_suffix = parsed_dt.strftime("%H-%M-%S")     # e.g., "09-35-49"

    # 5. Build clean, human-readable directory tree
    TARGET_DIR = os.path.join(UPLOAD_DIR, meta_inst, date_folder)
    os.makedirs(TARGET_DIR, exist_ok=True)

    # 6. Construct structural file paths using the guaranteed-unique time suffix
    meta_save_path = os.path.join(TARGET_DIR, f"{experiment_name}_{time_suffix}_metadata.json")
    data_save_path = os.path.join(TARGET_DIR, f"{experiment_name}_{time_suffix}_data.json")

    # 7. Physical write to hard drive
    metadata_content = await metadata_file.read()
    with open(meta_save_path, "wb") as f:
        f.write(metadata_content)
    data_content = await data_file.read()
    with open(data_save_path, "wb") as f:
        f.write(data_content)

    # 8. Log the strings into Postgres
    save_pair_to_db(user_id, instrument_id, experiment_name, meta_save_path, data_save_path)

    return {
        "status": "success", 
        "message": f"Saved. Instrument context resolved to ID: {instrument_id}"
    }


@app.get("/tests/by-instrument/{model_name}")
async def list_tests_by_instrument(model_name: str):
    results = get_tests_by_instrument(model_name)
    if not results:
        return {"message": f"No tests found generated by instrument '{model_name}'", "tests": []}
    return {"instrument": model_name, "count": len(results), "tests": results}

@app.get("/tests/by-user/{username}")
async def list_tests_by_user(username: str):
    results = get_tests_by_user(username)
    if not results:
        return {"message": f"No tests found uploaded by user '{username}'", "tests": []}
    return {"user": username, "count": len(results), "tests": results}
