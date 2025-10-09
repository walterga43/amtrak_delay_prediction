import schedule
import time
import pandas as pd
from datetime import datetime
import os
from data_collector import AmtrackDataCollector

class HistoricalDataManager:
  def __init__(self, data_dir='data'):
    self.data_dir = data_dir
    self.collector = AmtrackDataCollector('data/raw/raw.json')

  def collect_and_store(self):
    print(f"[{datetime.now()}] Starting data collection...")

    try:
      raw = self.collector.get_train_data()
      if raw:
        station_df = self.process_station_data(raw)
        train_df = self.process_train_data(raw)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print(f"Collected {len(station_df)} station records, {len(train_df)} train records")

        self.append_to_master(station_df, train_df)
    except Exception as e:
      print(f"Error during collection: {e}")


  def process_station_data(self, raw_data):
    station_records = []
    for train_number, train_list in raw_data.items():
      for train in train_list:
        route_name = train.get('routeName', '')
        train_id = train.get('trainID', '')
      
        for station in train.get('stations', []):
          station_record = {
            'collection_timestamp': datetime.now(),
            'train_number': train_number,
            'train_id': train_id,
            'route_name': route_name,
            'station_name': station.get('name', ''),
            'station_code': station.get('code', ''),
            'scheduled_arrival': station.get('schArr'),
            'actual_arrival': station.get('arr'),
            'scheduled_departure': station.get('schDep'),
            'actual_departure': station.get('dep'),
            'status': station.get('status', ''),
            'timezone': station.get('tz', ''),
          }
          station_records.append(station_record)

    df = pd.DataFrame(station_records)

    time_columns = ['scheduled_arrival', 'actual_arrival', 'scheduled_departure', 'actual_departure']
    for col in time_columns:
      df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)

    df["departure_delay_minutes"] = (df['actual_departure']- df['scheduled_departure']).dt.total_seconds() / 60
    df["arrival_delay_minutes"] = (df['actual_arrival'] - df['scheduled_arrival']).dt.total_seconds() / 60

    return df
  def process_train_data(self, raw_data):
    train_records = []
    for train_number, train_list in raw_data.items():
      for train in train_list:
        train_record = {
          'collection_timestamp': datetime.now(),
          'train_number': train_number,
          'route_name': train.get('routeName', ''),
          'train_id': train.get('trainID', ''),
          'lat': train.get('lat'),
          'lon': train.get('lon'),
          'heading': train.get('heading', ''),
          'velocity': train.get('velocity'),
          'train_state': train.get('trainState', ''),
          'status_msg': train.get('statusMsg', ''),
          'origin_code': train.get('origCode', ''),
          'dest_code': train.get('destCode', ''),
          'num_stations': len(train.get('stations', []))
        }
        train_records.append(train_record)
    df = pd.DataFrame(train_records)
    return df

  def append_to_master(self, station_df, train_df):
    master_stations_file = f"{self.data_dir}/historical/all_stations.csv"
    if os.path.exists(master_stations_file):
      station_df.to_csv(master_stations_file, mode='a', header=False, index=False)
    else:
      station_df.to_csv(master_stations_file, index=False)

    master_train_file = f"{self.data_dir}/historical/all_trains.csv"
    if os.path.exists(master_train_file):
      train_df.to_csv(master_train_file, mode='a', header=False, index=False)
    else:
      train_df.to_csv(master_train_file, index=False)

  def get_historical_data(self, days_back=7):
    master_file = f"{self.data_dir}/historical/all_stations.csv"

    if os.path.exists(master_file):
      df = pd.read_csv(master_file)
      df['collection_timestamp'] = pd.to_datetime(df['collection_timestamp'])
      cutoff_date = datetime.now() - pd.Timedelta(days=days_back)
      recent_data = df[df['collection_timestamp'] >= cutoff_date]
      
      print(f"Loaded {len(recent_data)} records from last {days_back} days")
      return recent_data
    else:
      print("No historical data found")
      return pd.DataFrame()
    
  def start_automated_collection(self):
    print("Starting data collection")
    print("Data will be collected at 30 minute intervals (press CRTL + C to stop)")

    schedule.every(30).minutes.do(self.collect_and_store)
    self.collect_and_store()

    while True:
      schedule.run_pending()
      time.sleep(60)

if __name__ == "__main__":
    manager = HistoricalDataManager()
    manager.start_automated_collection()