import os
import shutil
import glob
from log_parser import parse_file
from database import get_connection, get_or_create_device
from processing import process_device_snapshots

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

def ingest_files():
    # Detect device folders in data/ (excluding special folders like 'db', 'processed')
    reserved = {'db', 'processed', 'input'} 
    
    device_folders = [
        d for d in os.listdir(DATA_DIR) 
        if os.path.isdir(os.path.join(DATA_DIR, d)) and d not in reserved and not d.startswith('.')
    ]
    
    conn = get_connection()
    cursor = conn.cursor()
    
    files_processed_count = 0
    
    for device_folder in device_folders:
        device_path = os.path.join(DATA_DIR, device_folder)
        
        # Clean device name (remove "Activity " prefix)
        device_name_clean = device_folder.replace("Activity ", "").strip()
        
        # Get or create device ID
        device_id = get_or_create_device(device_name_clean)
        
        # Find all .txt or .md files
        txt_files = glob.glob(os.path.join(device_path, "*.txt")) + glob.glob(os.path.join(device_path, "*.md"))
        
        device_updated = False

        for filepath in txt_files:
            print(f"Processing {filepath}...")
            
            try:
                snapshots = parse_file(filepath)
                if not snapshots:
                    print(f"Skipping {filepath}: No valid snapshots found.")
                    continue
                
                print(f"  Found {len(snapshots)} snapshots.")
                
                file_has_new_data = False
                
                for timestamp, data_dict in snapshots:
                    # Check if snapshot already exists (deduplication by timestamp)
                    cursor.execute(
                        "SELECT id FROM raw_snapshots WHERE device_id = ? AND timestamp = ?",
                        (device_id, timestamp.isoformat())
                    )
                    if cursor.fetchone():
                        # print(f"  Snapshot for {timestamp} already exists. Skipping.")
                        continue
                    
                    # Insert Snapshot
                    cursor.execute(
                        "INSERT INTO raw_snapshots (device_id, timestamp, file_source) VALUES (?, ?, ?)",
                        (device_id, timestamp.isoformat(), os.path.basename(filepath))
                    )
                    snapshot_id = cursor.lastrowid
                    
                    # Insert Entries
                    entries = []
                    for app, seconds in data_dict.items():
                        entries.append((snapshot_id, app, seconds))
                    
                    cursor.executemany(
                        "INSERT INTO raw_snapshot_entries (snapshot_id, app_name, cumulative_seconds) VALUES (?, ?, ?)",
                        entries
                    )
                    file_has_new_data = True
                
                if file_has_new_data:
                    conn.commit()
                    device_updated = True
            
                # Move to processed (flat structure)
                os.makedirs(PROCESSED_DIR, exist_ok=True)
                dest_path = os.path.join(PROCESSED_DIR, os.path.basename(filepath))
                
                # Handle filename collision in processed
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(os.path.basename(filepath))
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(PROCESSED_DIR, f"{base}_{counter}{ext}")
                        counter += 1
                
                shutil.move(filepath, dest_path)
                
            except Exception as e:
                print(f"Error processing {filepath}: {e}")
                
        # Trigger reprocessing of intervals for this device if we ingested new data
        if device_updated:
            print(f"Recalculating intervals for {device_name_clean}...")
            process_device_snapshots(device_id)

        # Check if folder is empty (ignoring .DS_Store) and remove it if so
        remaining_files = [f for f in os.listdir(device_path) if f != '.DS_Store']
        if not remaining_files:
            print(f"Removing processed folder: {device_path}")
            shutil.rmtree(device_path)

    conn.close()
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_files()
