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

if __name__ == "__main__":
    init_db()
