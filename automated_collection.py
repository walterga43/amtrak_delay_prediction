import os
import time
from datetime import datetime

import pandas as pd
import schedule

from data_collector import AmtrackDataCollector

# Column order of the master CSVs. Rows are always written in this order so
# appended data lines up with the existing header.
STATION_COLUMNS = [
  'train_number', 'train_id', 'route_name', 'station_name', 'station_code',
  'scheduled_arrival', 'actual_arrival', 'scheduled_departure', 'actual_departure',
  'status', 'timezone', 'departure_delay_minutes', 'arrival_delay_minutes',
  'collection_timestamp',
]
TRAIN_COLUMNS = [
  'train_number', 'route_name', 'train_id', 'lat', 'lon', 'heading', 'velocity',
  'train_state', 'status_msg', 'origin_code', 'dest_code', 'num_stations',
  'collection_timestamp',
]
TIME_COLUMNS = ['scheduled_arrival', 'actual_arrival', 'scheduled_departure', 'actual_departure']


STOP_KEY = ['train_id', 'station_code', 'scheduled_departure']


class HistoricalDataManager:
  def __init__(self, data_dir='data'):
    self.data_dir = data_dir
    self.historical_dir = os.path.join(data_dir, 'historical')
    self.stations_file = os.path.join(self.historical_dir, 'all_stations.csv')
    self.trains_file = os.path.join(self.historical_dir, 'all_trains.csv')
    self.collector = AmtrackDataCollector(os.path.join(data_dir, 'raw', 'raw.json'))

  def collect_and_store(self):
    collection_time = datetime.now().replace(microsecond=0)
    print(f"[{collection_time}] Starting data collection...")

    try:
      raw = self.collector.get_train_data()
      if raw:
        station_df = self.process_station_data(raw, collection_time)
        train_df = self.process_train_data(raw, collection_time)

        print(f"Collected {len(station_df)} station records, {len(train_df)} train records")

        self.append_to_master(station_df, train_df)
    except Exception as e:
      print(f"Error during collection: {e}")

  def process_station_data(self, raw_data, collection_time=None):
    collection_time = collection_time or datetime.now().replace(microsecond=0)
    station_records = []
    for train_number, train_list in raw_data.items():
      for train in train_list:
        route_name = train.get('routeName', '')
        train_id = train.get('trainID', '')

        for station in train.get('stations', []):
          station_records.append({
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
            'collection_timestamp': collection_time,
          })

    df = pd.DataFrame(station_records, columns=[c for c in STATION_COLUMNS if not c.endswith('_minutes')])

    for col in TIME_COLUMNS:
      df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)

    df['departure_delay_minutes'] = (df['actual_departure'] - df['scheduled_departure']).dt.total_seconds() / 60
    df['arrival_delay_minutes'] = (df['actual_arrival'] - df['scheduled_arrival']).dt.total_seconds() / 60

    return df[STATION_COLUMNS]

  def process_train_data(self, raw_data, collection_time=None):
    collection_time = collection_time or datetime.now().replace(microsecond=0)
    train_records = []
    for train_number, train_list in raw_data.items():
      for train in train_list:
        train_records.append({
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
          'num_stations': len(train.get('stations', [])),
          'collection_timestamp': collection_time,
        })
    return pd.DataFrame(train_records, columns=TRAIN_COLUMNS)

  def append_to_master(self, station_df, train_df):
    os.makedirs(self.historical_dir, exist_ok=True)
    self._append_csv(station_df, self.stations_file)
    self._append_csv(train_df, self.trains_file)

  @staticmethod
  def _append_csv(df, path):
    """Append df to path, matching the column order of the existing header."""
    if not os.path.exists(path):
      df.to_csv(path, index=False)
      return
    existing_columns = pd.read_csv(path, nrows=0).columns.tolist()
    if set(existing_columns) != set(df.columns):
      raise ValueError(f"Columns in {path} do not match the new data: {existing_columns} vs {list(df.columns)}")
    df[existing_columns].to_csv(path, mode='a', header=False, index=False)

  def get_historical_data(self, days_back=None):
    if not os.path.exists(self.stations_file):
      print("No historical data found")
      return pd.DataFrame(columns=STATION_COLUMNS)

    df = pd.read_csv(self.stations_file, low_memory=False)
    df['collection_timestamp'] = pd.to_datetime(df['collection_timestamp'], format='ISO8601')
    for col in TIME_COLUMNS:
      df[col] = pd.to_datetime(df[col], errors='coerce', utc=True, format='ISO8601')

    if days_back is not None:
      cutoff_date = datetime.now() - pd.Timedelta(days=days_back)
      df = df[df['collection_timestamp'] >= cutoff_date]

    print(f"Loaded {len(df)} records" + (f" from last {days_back} days" if days_back is not None else ""))
    return df

  def get_unique_stops(self, days_back=None, departed_only=True):
    """
    One row per stop per train run, taken from the latest collection that saw it.

    Adds `run_id` (train_id + origin departure date, since train IDs repeat
    every month) and `stop_number` (the stop's position along its route).
    With departed_only=True, only stops the train has already left are kept,
    so delays are actual rather than the API's estimates for future stops.
    """
    df = self.get_historical_data(days_back)
    if df.empty:
      return df

    snapshot = ['collection_timestamp', 'train_id']
    origin = df.groupby(snapshot)['scheduled_departure'].transform('min')
    df['run_id'] = df['train_id'].astype(str) + '_' + origin.dt.strftime('%Y%m%d')
    df['stop_number'] = df.groupby(snapshot)['scheduled_departure'].rank(method='first')

    stops = (df.sort_values('collection_timestamp')
               .drop_duplicates(STOP_KEY, keep='last')
               .dropna(subset=['departure_delay_minutes']))
    if departed_only:
      stops = stops[stops['status'] == 'Departed']

    print(f"{len(stops)} unique stops from {stops['run_id'].nunique()} train runs")
    return stops.reset_index(drop=True)

  def start_automated_collection(self):
    print("Starting data collection")
    print("Data will be collected at 30 minute intervals (press CTRL + C to stop)")

    schedule.every(30).minutes.do(self.collect_and_store)
    self.collect_and_store()

    while True:
      schedule.run_pending()
      time.sleep(60)


if __name__ == "__main__":
  manager = HistoricalDataManager()
  manager.start_automated_collection()
