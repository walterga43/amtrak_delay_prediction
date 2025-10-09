import pandas as pd
import os
from datetime import datetime

def cleanup_stations_csv(filepath='data/historical/all_stations.csv'):
    """
    One-time cleanup script to fix corrupted rows in all_stations.csv
    Creates a backup before cleaning.
    """
    
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        return
    
    # Create backup
    backup_path = filepath.replace('.csv', '_backup.csv')
    print(f"Creating backup at {backup_path}...")
    
    # Read the original file
    import shutil
    shutil.copy2(filepath, backup_path)
    print("Backup created successfully!")
    
    # Read the CSV
    print("\nReading CSV file...")
    df = pd.read_csv(filepath, low_memory=False)
    initial_rows = len(df)
    print(f"Initial rows: {initial_rows}")
    
    # Identify corrupted rows where train_number looks like a timestamp
    # Normal train_number should be just a number (e.g., "1", "2", "91")
    # Corrupted rows have train_number like "2025-10-02 12:32:43.590284"
    print("\nIdentifying corrupted rows...")
    mask = df['train_number'].astype(str).str.contains(r'\d{4}-\d{2}-\d{2}', na=False, regex=True)
    corrupted_count = mask.sum()
    
    print(f"Found {corrupted_count} corrupted rows with shifted columns")
    
    if corrupted_count > 0:
        # Show some examples
        print("\nExample of corrupted row:")
        print(df[mask].iloc[0])
        
        # Remove corrupted rows
        df_clean = df[~mask].copy()
        print(f"\nRemoved {corrupted_count} corrupted rows")
    else:
        df_clean = df.copy()
        print("No corrupted rows found!")
    
    # Additional cleanup: check for invalid timestamps in collection_timestamp column
    print("\nChecking collection_timestamp validity...")
    df_clean['collection_timestamp'] = pd.to_datetime(df_clean['collection_timestamp'], errors='coerce')
    
    invalid_timestamps = df_clean['collection_timestamp'].isna().sum()
    if invalid_timestamps > 0:
        print(f"Found {invalid_timestamps} rows with invalid timestamps")
        df_clean = df_clean.dropna(subset=['collection_timestamp'])
        print(f"Removed {invalid_timestamps} rows with invalid timestamps")
    
    # Convert timestamps back to string format for CSV storage
    df_clean['collection_timestamp'] = df_clean['collection_timestamp'].astype(str)
    
    # Final stats
    final_rows = len(df_clean)
    rows_removed = initial_rows - final_rows
    
    print("\n" + "="*50)
    print("CLEANUP SUMMARY")
    print("="*50)
    print(f"Initial rows:     {initial_rows}")
    print(f"Final rows:       {final_rows}")
    print(f"Rows removed:     {rows_removed}")
    print(f"Rows retained:    {final_rows / initial_rows * 100:.1f}%")
    print("="*50)
    
    # Save cleaned data
    print(f"\nSaving cleaned data to {filepath}...")
    df_clean.to_csv(filepath, index=False)
    print("Cleanup complete!")
    
    # Show date range of valid data
    df_clean['collection_timestamp'] = pd.to_datetime(df_clean['collection_timestamp'])
    print(f"\nData date range:")
    print(f"  Earliest: {df_clean['collection_timestamp'].min()}")
    print(f"  Latest:   {df_clean['collection_timestamp'].max()}")
    
    return df_clean

if __name__ == "__main__":
    print("AMTRAK DATA CLEANUP SCRIPT")
    print("This script will clean corrupted rows from all_stations.csv")
    print("A backup will be created before any changes are made.\n")
    
    response = input("Continue with cleanup? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        cleanup_stations_csv()
    else:
        print("Cleanup cancelled.")