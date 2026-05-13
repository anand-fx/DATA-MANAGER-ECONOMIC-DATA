import pandas as pd
import os
import glob
import re
import io

# 1. Configuration
input_dir = r'D:\ECONOMICDATA\EUR' 
output_base_dir = 'processed_macro_data'

def clean_filename(text):
    return re.sub(r'[^\w\s-]', '', str(text)).strip().replace(' ', '_')

all_csv_files = glob.glob(os.path.join(input_dir, "*.csv"))
all_data = []

print(f"Deep-cleaning {len(all_csv_files)} files...")

for file in all_csv_files:
    try:
        # Step A: Read the file as raw bytes first to handle weird encodings
        with open(file, 'rb') as f:
            raw_data = f.read()
        
        # Try different encodings to decode the bytes into a string
        decoded_content = None
        for encoding in ['utf-8-sig', 'utf-16', 'latin1', 'cp1252']:
            try:
                decoded_content = raw_data.decode(encoding)
                if 'event_date' in decoded_content.lower():
                    break
            except:
                continue
        
        if not decoded_content:
            print(f"Error: Could not decode {os.path.basename(file)}")
            continue

        # Step B: Find the line containing 'event_date'
        lines = decoded_content.splitlines()
        data_start_idx = 0
        for i, line in enumerate(lines):
            if 'event_date' in line.lower():
                data_start_idx = i
                break
        
        # Step C: Reconstruct the CSV from the header onwards
        clean_csv_string = "\n".join(lines[data_start_idx:])
        
        # Load the clean string into Pandas
        df = pd.read_csv(io.StringIO(clean_csv_string), sep=None, engine='python', on_bad_lines='skip')
        
        # Standardize column names (remove quotes and non-alpha characters)
        df.columns = [re.sub(r'\W+', '', c.strip().lower()) for c in df.columns]
        
        # Map back to expected names if stripping removed underscores
        if 'eventdate' in df.columns: df.rename(columns={'eventdate': 'event_date'}, inplace=True)
        if 'eventname' in df.columns: df.rename(columns={'eventname': 'event'}, inplace=True)

        if not df.empty and 'event_date' in df.columns:
            print(f"Successfully loaded {os.path.basename(file)} ({len(df)} rows)")
            all_data.append(df)
        else:
            print(f"Warning: Missing 'event_date' column in {os.path.basename(file)}. Found: {list(df.columns)}")
            
    except Exception as e:
        print(f"Error reading {file}: {e}")

if not all_data:
    print("\nFAILED: No data could be parsed. Check if 'event_date' is spelled correctly in the CSVs.")
    exit()

# Combine and Process
master_df = pd.concat(all_data, ignore_index=True)
master_df['event_date'] = pd.to_datetime(master_df['event_date'], errors='coerce')
master_df = master_df.dropna(subset=['event_date', 'event', 'currency'])

# Output separation logic
for curr in master_df['currency'].unique():
    curr_str = str(curr).upper().strip()
    curr_path = os.path.join(output_base_dir, curr_str)
    os.makedirs(curr_path, exist_ok=True)
    
    curr_df = master_df[master_df['currency'] == curr]
    
    # Filtering for High/Medium impact events
    if 'impact' in curr_df.columns:
        red_folders = curr_df[curr_df['impact'].astype(str).str.contains('High|Medium|Red', case=False, na=False)]
    else:
        red_folders = curr_df

    for event in red_folders['event'].unique():
        event_df = red_folders[red_folders['event'] == event]
        event_df = event_df.sort_values('event_date')
        
        # Clean event name from month suffix (e.g. "PMI (Dec)")
        clean_event_name = re.sub(r'\s\(\w+\/?\w*\)$', '', str(event)).strip()
        
        safe_file_name = clean_filename(clean_event_name)
        file_path = os.path.join(curr_path, f"{safe_file_name}.csv")
        event_df.to_csv(file_path, index=False)

print(f"\nSUCCESS! Check the '{output_base_dir}' folder.")
