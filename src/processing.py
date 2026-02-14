from datetime import datetime
import sqlite3
from database import get_connection

def process_device_snapshots(device_id):
    """
    Recalculates intervals for a given device based on raw snapshots.
    Optimized to only process new snapshots if possible, but for robustness
    we might re-evaluate the chain or find the last processed point.
    
    For simplicity in this V1:
    1. Fetch all raw snapshots for the device ordered by timestamp.
    2. Iterate and calculate diffs.
    3. Update usage_intervals (delete old for this device and re-insert? Or merge?)
       -> Deleting and re-inserting is safer for consistency if we expect out-of-order inserts.
       -> However, if data is large, this is inefficient.
       -> Better: find the latest interval end_time, and start processing snapshots after that.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get all snapshots ordered by time
    cursor.execute("""
        SELECT id, timestamp FROM raw_snapshots 
        WHERE device_id = ? ORDER BY timestamp ASC
    """, (device_id,))
    snapshots = cursor.fetchall()
    
    if not snapshots:
        conn.close()
        return

    # Clear existing intervals for this device to ensure consistency (Full Rebuild Approach)
    # In a production system with millions of rows, we'd do incremental updates.
    cursor.execute("DELETE FROM usage_intervals WHERE device_id = ?", (device_id,))
    
    # Cache entries for each snapshot to avoid N+1 queries
    # Structure: {snapshot_id: {app_name: cumulative_seconds}}
    snapshot_data = {}
    
    # Fetch all entries for this device
    cursor.execute("""
        SELECT se.snapshot_id, se.app_name, se.cumulative_seconds
        FROM raw_snapshot_entries se
        JOIN raw_snapshots s ON se.snapshot_id = s.id
        WHERE s.device_id = ?
    """, (device_id,))
    
    for row in cursor.fetchall():
        snap_id, app, seconds = row
        if snap_id not in snapshot_data:
            snapshot_data[snap_id] = {}
        snapshot_data[snap_id][app] = seconds

    intervals_to_insert = []

    # Logic:
    # Interval = Snap[i] - Snap[i-1]
    # IF same day AND Snap[i] >= Snap[i-1]
    
    # We iterate from index 1.
    # What about the very first snapshot of the day?
    # Ideally, we'd have a snapshot at 00:00:00 with 0 usage.
    # If we don't, the first snapshot IS the usage from 00:00 to T_first.
    # So we should treat "start of day" as implicit previous snapshot with 0 usage.

    for i, (curr_id, curr_ts_str) in enumerate(snapshots):
        # Skip the very first snapshot (no prior baseline) to avoid assuming usage started at 00:00
        if i == 0:
            continue

        # Convert timestamp string back to datetime object
        curr_ts = datetime.fromisoformat(curr_ts_str)
        curr_apps = snapshot_data.get(curr_id, {})
        
        prev_ts = None
        prev_apps = {}
        
        if i > 0:
            prev_id, prev_ts_str = snapshots[i-1]
            prev_ts = datetime.fromisoformat(prev_ts_str)
            prev_apps = snapshot_data.get(prev_id, {})
            
        # Determine start time and previous usage baseline
        if prev_ts and prev_ts.date() == curr_ts.date():
            # Same day: Diff from previous snapshot
            step_start = prev_ts
            base_usage = prev_apps
        else:
            # Different day (New day): Diff from 0 (implicitly from midnight-ish, or just T=0)
            # Implicit usage: The snapshot represents usage from 00:00?
            # Or assume start time is midnight?
            # Let's assume start time is midnight of that day for the first interval.
            step_start = datetime.combine(curr_ts.date(), datetime.min.time())
            base_usage = {} # 0 usage baseline
            
        # Calculate intervals for each app in current snapshot
        for app, curr_seconds in curr_apps.items():
            prev_seconds = base_usage.get(app, 0)
            delta = curr_seconds - prev_seconds
            
            if delta > 0:
                intervals_to_insert.append((
                    device_id,
                    step_start.isoformat(),
                    curr_ts.isoformat(),
                    app,
                    delta
                ))
            elif delta < 0:
                # Anomaly: usage decreased? 
                # Could be a device reset, or manual deletion of history.
                # Log warning? For now, we ignore negative deltas or treat as 0.
                pass

    if intervals_to_insert:
        cursor.executemany("""
            INSERT INTO usage_intervals 
            (device_id, start_time, end_time, app_name, duration_seconds)
            VALUES (?, ?, ?, ?, ?)
        """, intervals_to_insert)

    conn.commit()
    conn.close()
    print(f"Processed {len(intervals_to_insert)} intervals for device {device_id}")
