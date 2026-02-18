import sqlite3
import os
from datetime import datetime

# Resolve data directory relative to this file (in src/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "db", "screentime.db")

def get_connection():
    print(f"DEBUG: Connecting to DB at: {DB_PATH}")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Devices table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );
    """)

    # Raw Snapshots (Metadata of a file import)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        timestamp DATETIME NOT NULL,
        file_source TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (device_id) REFERENCES devices(id),
        UNIQUE(device_id, timestamp)
    );
    """)

    # Raw Snapshot Entries (The actual app usage data in a snapshot)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_snapshot_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        app_name TEXT NOT NULL,
        cumulative_seconds INTEGER NOT NULL,
        FOREIGN KEY (snapshot_id) REFERENCES raw_snapshots(id) ON DELETE CASCADE
    );
    """)

    # Usage Intervals (Processed data: calculated usage between snapshots)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usage_intervals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        start_time DATETIME NOT NULL,
        end_time DATETIME NOT NULL,
        app_name TEXT NOT NULL,
        duration_seconds INTEGER NOT NULL,
        FOREIGN KEY (device_id) REFERENCES devices(id)
    );
    """)

    # App Categories table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        alias TEXT
    );
    """)
    
    # Simple migration check: try to add column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE app_categories ADD COLUMN alias TEXT")
    except sqlite3.OperationalError:
        # Column likely already exists
        pass

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

def get_or_create_device(device_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM devices WHERE name = ?", (device_name,))
    row = cursor.fetchone()
    if row:
        device_id = row[0]
    else:
        cursor.execute("INSERT INTO devices (name) VALUES (?)", (device_name,))
        device_id = cursor.lastrowid
        conn.commit()
    conn.close()
    return device_id

# --- Category Management Helpers ---

def get_all_categories():
    """Returns a dict {app_name: {'category': category, 'alias': alias}}."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT app_name, category, alias FROM app_categories")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: {'category': row[1], 'alias': row[2]} for row in rows}

def update_app_category(app_name, category, alias=None):
    """Updates or inserts a category and alias for an app."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO app_categories (app_name, category, alias) 
        VALUES (?, ?, ?)
        ON CONFLICT(app_name) DO UPDATE SET 
            category=excluded.category,
            alias=excluded.alias
    """, (app_name, category, alias))
    conn.commit()
    conn.close()

def get_uncategorized_apps():
    """
    Returns a list of app names that exist in usage_intervals but not in app_categories.
    Ordered by total duration (descending) to prioritize most used apps.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT u.app_name, SUM(u.duration_seconds) as total_duration
        FROM usage_intervals u
        LEFT JOIN app_categories c ON u.app_name = c.app_name
        WHERE c.category IS NULL
        GROUP BY u.app_name
        ORDER BY total_duration DESC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

if __name__ == "__main__":
    init_db()
