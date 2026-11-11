"""
Train and evaluate a Random Forest that predicts departure delay (minutes) at a stop.

Evaluation design:
  * The API returns every stop of every active train on each 30-minute call, so
    one stop appears in many collections. We keep one row per stop
    (HistoricalDataManager.get_unique_stops) so identical rows can't land in
    both the training and test sets.
  * Only stops the train has already departed are used, so the target is an
    actual delay rather than the API's estimate for a future stop. A handful
    of records claiming departures over an hour early are dropped as errors.
  * The train/test split is by train run: every stop of a given run goes to the
    same side. Delays within a run are strongly correlated (a train that is
    late at stop 5 is late at stop 6), so a random row split would leak.
  * The model is compared against two baselines: predicting the overall
    average delay, and predicting each route's average delay.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

from automated_collection import HistoricalDataManager

RANDOM_STATE = 42
OUTPUT_IMAGE = 'images/model_performance.png'

MIN_PLAUSIBLE_DELAY = -60
CATEGORICAL_FEATURES = ['route_name', 'station_code', 'train_number']
NUMERIC_FEATURES = ['stop_number', 'local_hour', 'day_of_week']
FEATURE_LABELS = {
  'route_name': 'Route',
  'station_code': 'Station',
  'train_number': 'Train number',
  'stop_number': 'Stop # along route',
  'local_hour': 'Scheduled hour (local)',
  'day_of_week': 'Day of week',
}


def add_local_time_features(df):
  """Hour and weekday of the scheduled departure in the station's own timezone."""
  local_hour = pd.Series(index=df.index, dtype=float)
  day_of_week = pd.Series(index=df.index, dtype=float)
  for tz, group in df.groupby('timezone'):
    local = group['scheduled_departure'].dt.tz_convert(tz)
    local_hour[group.index] = local.dt.hour
    day_of_week[group.index] = local.dt.day_of_week
  df['local_hour'] = local_hour
  df['day_of_week'] = day_of_week
  return df


def build_features(stops):
  df = add_local_time_features(stops.copy())
  features = pd.DataFrame(index=df.index)
  for col in CATEGORICAL_FEATURES:
    features[col] = df[col].astype(str).astype('category').cat.codes
  for col in NUMERIC_FEATURES:
    features[col] = df[col]
  return features, df['departure_delay_minutes'], df


def make_model():
  return RandomForestRegressor(
    n_estimators=200,
    min_samples_leaf=5,
    random_state=RANDOM_STATE,
    n_jobs=-1,
  )


def baseline_predictions(y_train, routes_train, routes_test):
  overall = np.full(len(routes_test), y_train.mean())
  route_means = y_train.groupby(routes_train.values).mean()
  by_route = routes_test.map(route_means).fillna(y_train.mean()).values
  return overall, by_route


def cross_validate(X, y, routes, groups, n_splits=5):
  rows = []
  for fold, (tr, te) in enumerate(GroupKFold(n_splits=n_splits).split(X, y, groups)):
    overall, by_route = baseline_predictions(y.iloc[tr], routes.iloc[tr], routes.iloc[te])
    y_pred = make_model().fit(X.iloc[tr], y.iloc[tr]).predict(X.iloc[te])
    for name, pred in [('Overall average', overall), ('Route average', by_route), ('Random Forest', y_pred)]:
      rows.append({'fold': fold, **evaluate(name, y.iloc[te], pred)})
  summary = pd.DataFrame(rows).groupby('model', sort=False)[['MAE (min)', 'R²']].agg(['mean', 'std'])
  return summary


def evaluate(name, y_true, y_pred):
  return {
    'model': name,
    'MAE (min)': mean_absolute_error(y_true, y_pred),
    'RMSE (min)': np.sqrt(mean_squared_error(y_true, y_pred)),
    'R²': r2_score(y_true, y_pred),
  }


def plot_results(model, feature_names, y_test, y_pred, results):
  fig, axes = plt.subplots(2, 2, figsize=(14, 10))

  # 1. Feature importance
  ax = axes[0, 0]
  importance = pd.Series(model.feature_importances_, index=[FEATURE_LABELS[f] for f in feature_names]).sort_values()
  ax.barh(importance.index, importance.values, color='steelblue')
  ax.set_title('Feature Importance', fontweight='bold')
  ax.set_xlabel('Importance')

  # 2. MAE vs. baselines
  ax = axes[0, 1]
  colors = ['lightgray'] * (len(results) - 1) + ['steelblue']
  bars = ax.bar(results['model'], results['MAE (min)'], color=colors, edgecolor='black')
  ax.bar_label(bars, fmt='%.1f')
  ax.set_title('Mean Absolute Error on Held-out Train Runs', fontweight='bold')
  ax.set_ylabel('Minutes (lower is better)')

  # 3. Actual vs predicted
  ax = axes[1, 0]
  ax.scatter(y_test, y_pred, alpha=0.4, s=12, color='darkgreen')
  lo, hi = min(y_test.min(), y_pred.min()), max(y_test.max(), y_pred.max())
  ax.plot([lo, hi], [lo, hi], 'r--', lw=2, label='Perfect prediction')
  ax.set_title('Actual vs Predicted Delay', fontweight='bold')
  ax.set_xlabel('Actual delay (minutes)')
  ax.set_ylabel('Predicted delay (minutes)')
  ax.legend()

  # 4. Residuals
  ax = axes[1, 1]
  ax.hist(y_test - y_pred, bins=50, color='purple', alpha=0.7, edgecolor='black')
  ax.axvline(0, color='red', linestyle='--', lw=2)
  ax.set_title('Prediction Errors (Actual − Predicted)', fontweight='bold')
  ax.set_xlabel('Minutes')
  ax.set_ylabel('Stops')

  fig.suptitle('Train Delay Prediction: Random Forest vs Baselines', fontsize=16, fontweight='bold')
  fig.tight_layout()
  fig.savefig(OUTPUT_IMAGE, dpi=150, bbox_inches='tight')
  print(f"\nSaved {OUTPUT_IMAGE}")
  plt.show()


def main():
  print("Loading data...")
  stops = HistoricalDataManager().get_unique_stops(departed_only=True)
  implausible = stops['departure_delay_minutes'] < MIN_PLAUSIBLE_DELAY
  print(f"Dropping {implausible.sum()} stops that 'departed' over {-MIN_PLAUSIBLE_DELAY} minutes early (API data errors)")
  X, y, df = build_features(stops[~implausible])
  groups = df['run_id']

  print(f"Days covered: {sorted(df['scheduled_departure'].dt.date.astype(str).unique())}")
  print(f"Routes: {df['route_name'].nunique()}, stations: {df['station_code'].nunique()}")

  splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=RANDOM_STATE)
  train_idx, test_idx = next(splitter.split(X, y, groups))
  X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
  y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
  print(f"Train: {len(X_train)} stops from {groups.iloc[train_idx].nunique()} runs | "
        f"Test: {len(X_test)} stops from {groups.iloc[test_idx].nunique()} runs")

  routes = df['route_name']
  overall_mean, route_pred = baseline_predictions(y_train, routes.iloc[train_idx], routes.iloc[test_idx])

  print("\nTraining Random Forest...")
  model = make_model().fit(X_train, y_train)
  y_pred = model.predict(X_test)

  results = pd.DataFrame([
    evaluate('Overall average', y_test, overall_mean),
    evaluate('Route average', y_test, route_pred),
    evaluate('Random Forest', y_test, y_pred),
  ])

  print("\n" + "=" * 60)
  print("RESULTS ON HELD-OUT TRAIN RUNS")
  print("=" * 60)
  print(results.to_string(index=False, float_format='%.2f'))
  print("=" * 60)

  print("\n5-fold grouped cross-validation (mean ± std across folds):")
  cv = cross_validate(X, y, routes, groups)
  for name, row in cv.iterrows():
    print(f"  {name:<16} MAE {row[('MAE (min)', 'mean')]:5.2f} ± {row[('MAE (min)', 'std')]:.2f}   "
          f"R² {row[('R²', 'mean')]:5.2f} ± {row[('R²', 'std')]:.2f}")

  importance = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
  print("\nFeature importance:")
  print(importance.rename(FEATURE_LABELS).to_string(float_format='%.3f'))

  plot_results(model, list(X.columns), y_test, y_pred, results)


if __name__ == '__main__':
  main()
