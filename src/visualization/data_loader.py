import pandas as pd
import sqlite3
import os
import sys

# Add src to path to import database module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import DB_PATH

def load_usage_data():
    """
    Loads usage data from the SQLite database into a Pandas DataFrame.
    """
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    
    query = """
    SELECT 
        u.start_time,
        u.end_time,
        u.app_name,
        u.duration_seconds,
        d.name as device_name,
        c.category,
        c.alias
    FROM usage_intervals u
    JOIN devices d ON u.device_id = d.id
    LEFT JOIN app_categories c ON u.app_name = c.app_name
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        return df

    # Convert timestamps to datetime
    df['start_time'] = pd.to_datetime(df['start_time'])
    df['end_time'] = pd.to_datetime(df['end_time'])
    
    # Enrich data
    df['date'] = df['start_time'].dt.date
    df['year'] = df['start_time'].dt.year
    df['hour'] = df['start_time'].dt.hour
    df['week'] = df['start_time'].dt.to_period('W').dt.start_time
    
    # Fill missing categories
    df['category'] = df['category'].fillna('Uncategorized')
    
    # Apply Aliasing: specific alias > original app_name
    df['original_app_name'] = df['app_name'] # Keep original for reference
    df['app_name'] = df['alias'].fillna(df['app_name'])
    
    return df
