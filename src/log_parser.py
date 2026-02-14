import re
from datetime import datetime

def parse_duration(duration_str):
    """
    Parses duration strings like "1h 30m", "45 min", "2h", "15m" into seconds.
    """
    total_seconds = 0
    duration_str = duration_str.lower().strip()
    
    # Check for hours
    hours_match = re.search(r'(\d+)\s*h', duration_str)
    if hours_match:
        total_seconds += int(hours_match.group(1)) * 3600
        
    # Check for minutes (m, min)
    minutes_match = re.search(r'(\d+)\s*(?:m|min)', duration_str)
    if minutes_match:
        total_seconds += int(minutes_match.group(1)) * 60
        
    # Check for seconds (s, sec) - less likely but possible
    seconds_match = re.search(r'(\d+)\s*(?:s|sec)', duration_str)
    if seconds_match:
        total_seconds += int(seconds_match.group(1))

    return total_seconds

def parse_header_date(header_line):
    """
    Parses the header line to extract the timestamp.
    Example: "13 Feb 2026 at 2:00 PM"
    """
    # Remove hidden characters often present in iOS copy/paste or file outputs
    # narrow no-break space \u202f is common in iOS time formats
    clean_line = header_line.replace('\u202f', ' ').encode('ascii', 'ignore').decode('utf-8').strip()
    
    # Try multiple formats
    formats = [
        "%d %b %Y at %I:%M %p", # 13 Feb 2026 at 2:00 PM
        "%d %B %Y at %H:%M",    # 13 February 2026 at 14:00
        "%Y-%m-%d %H:%M:%S",    # ISO
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(clean_line, fmt)
        except ValueError:
            continue
            
    # If standard formats fail, try with regex removal regarding "at" or similar
    try:
        if " at " in clean_line:
            return datetime.strptime(clean_line, "%d %b %Y at %I:%M %p")
    except ValueError:
        pass
        
    # print(f"Warning: Could not parse date header: '{header_line}' (cleaned: '{clean_line}')")
    return None

def parse_chunk(chunk_lines):
    """
    Parses a single block of lines associated with a timestamp.
    Returns: dict({app_name: duration_seconds})
    """
    data = {}
    
    # Rejoin lines to use the comma splitting logic
    body = "\n".join(chunk_lines)
    chunks = body.split(',')
    
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
            
        chunk_lines_inner = [l.strip() for l in chunk.splitlines() if l.strip()]
        if len(chunk_lines_inner) >= 2:
            title_line = chunk_lines_inner[0]
            seconds_line = chunk_lines_inner[1]
            
            # Extract App Name
            app_match = re.search(r'^(.*)\s*\(.*\)$', title_line)
            if app_match:
                app_name = app_match.group(1).strip()
            else:
                app_name = title_line.strip()
            
            # Extract Seconds
            sec_str = seconds_line.lower().replace('sec', '').strip()
            sec_str_clean = sec_str.replace(' ', '').replace('\u202f', '')
            
            try:
                seconds = float(sec_str_clean)
                data[app_name] = int(seconds)
            except ValueError:
                # print(f"Warning: Could not parse seconds from '{seconds_line}'")
                continue
    return data

def parse_file(filepath):
    """
    Parses a shortcut output file that may contain multiple snapshots.
    Returns:
        list of tuples: [(timestamp, dict({app_name: duration_seconds})), ...]
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    if not content:
        return []

    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if not lines:
        return []

    snapshots = []
    
    current_ts = None
    current_lines = []
    
    # Scan lines to find dates
    for line in lines:
        # Try to parse line as date
        ts = parse_header_date(line)
        
        if ts:
            # We found a new date header.
            # If we were accumulating lines for a previous snapshot, process it now.
            if current_ts:
                data = parse_chunk(current_lines)
                if data:
                    snapshots.append((current_ts, data))
            
            # Start new snapshot
            current_ts = ts
            current_lines = []
        else:
            # Not a date header, append to current block (if we have a started block)
            if current_ts:
                current_lines.append(line)
            else:
                # Ignore lines before the first date (e.g. Markdown headers)
                pass
                
    # Process the last block
    if current_ts:
        data = parse_chunk(current_lines)
        if data:
            snapshots.append((current_ts, data))

    return snapshots

if __name__ == "__main__":
    import sys
    # Direct test
    if len(sys.argv) > 1:
        results = parse_file(sys.argv[1])
        print(f"Found {len(results)} snapshots")
        for ts, parsed_data in results:
            print(f"-- Timestamp: {ts} --")
            for app, duration in list(parsed_data.items())[:3]:
                 print(f"   {app}: {duration}s")
            if len(parsed_data) > 3:
                print("   ...")
