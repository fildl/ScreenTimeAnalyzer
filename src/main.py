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
    # Detect device folders and files in data/ 
    reserved = {'db', 'processed', 'input'}
    
    # Map device_name -> list of file paths
    device_files_map = {}
    
    # Folders to cleanup (delete if empty)
    folders_to_cleanup = []

    print(f"Scanning {DATA_DIR} for new data...")

    # Safe check if DATA_DIR exists
    if not os.path.exists(DATA_DIR):
        print(f"Data directory {DATA_DIR} does not exist.")
        return

    for item in os.listdir(DATA_DIR):
        item_path = os.path.join(DATA_DIR, item)
        
        # Skip reserved or hidden
        if item in reserved or item.startswith('.'):
            continue
            
        if os.path.isdir(item_path):
            # It's a device folder (e.g. "Activity iPhone 13 mini")
            device_name = item.replace("Activity ", "").strip()
            files = glob.glob(os.path.join(item_path, "*.txt")) + glob.glob(os.path.join(item_path, "*.md"))
            
            if files:
                if device_name not in device_files_map:
                    device_files_map[device_name] = []
                device_files_map[device_name].extend(files)
            
            folders_to_cleanup.append(item_path)
            
        elif os.path.isfile(item_path):
            # It's a file directly in data/ (e.g. "Activity iPhone 13 mini.txt")
            if item.lower().endswith('.txt') or item.lower().endswith('.md'):
                filename_no_ext = os.path.splitext(item)[0]
                # Infer device name from filename
                if filename_no_ext.startswith("Activity "):
                    device_name = filename_no_ext.replace("Activity ", "").strip()
                else:
                    device_name = filename_no_ext.strip()
                
                if device_name not in device_files_map:
                    device_files_map[device_name] = []
                device_files_map[device_name].append(item_path)

    conn = get_connection()
    cursor = conn.cursor()
    
    for device_name, file_paths in device_files_map.items():
        print(f"Processing data for device: {device_name}")
        
        # Get or create device ID
        device_id = get_or_create_device(device_name)
        
        device_updated = False

        for filepath in file_paths:
            print(f"  Processing file: {filepath}")
            
            try:
                snapshots = parse_file(filepath)
                if not snapshots:
                    print(f"    Skipping {filepath}: No valid snapshots found.")
                    continue
                
                print(f"    Found {len(snapshots)} snapshots.")
                
                file_has_new_data = False
                
                for timestamp, data_dict in snapshots:
                    # Check if snapshot already exists (deduplication by timestamp)
                    cursor.execute(
                        "SELECT id FROM raw_snapshots WHERE device_id = ? AND timestamp = ?",
                        (device_id, timestamp.isoformat())
                    )
                    if cursor.fetchone():
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
            print(f"Recalculating intervals for {device_name}...")
            process_device_snapshots(device_id)

    # Cleanup empty folders
    for folder_path in folders_to_cleanup:
        try:
            if os.path.exists(folder_path):
                remaining_files = [f for f in os.listdir(folder_path) if f != '.DS_Store']
                if not remaining_files:
                    print(f"Removing empty folder: {folder_path}")
                    shutil.rmtree(folder_path)
        except Exception as e:
            print(f"Error cleaning up folder {folder_path}: {e}")

    conn.close()
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_files()
