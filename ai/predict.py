import fastf1
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error


def get_monaco_2025_predictions(cache_dir: str = "f1_cache") -> dict:
    """Return predictions for Monaco 2025 as a dictionary:
    {
      "predictions": [{"driver": str, "predicted_seconds": float}],
      "mae_seconds": float
    }
    """
    fastf1.Cache.enable_cache(cache_dir)

    session_2024 = fastf1.get_session(2024, "Monaco", "R")
    session_2024.load()

    laps_2024 = session_2024.laps[["Driver", "LapTime"]].copy()
    laps_2024.dropna(subset=["LapTime"], inplace=True)
    laps_2024["LapTime (s)"] = laps_2024["LapTime"].dt.total_seconds()

    qualifying_2025 = pd.DataFrame({
        "Driver": [
            "Lando Norris",
            "Oscar Piastri",
            "Max Verstappen",
            "George Russell",
            "Yuki Tsunoda",
            "Alexander Albon",
            "Charles Leclerc",
            "Lewis Hamilton",
            "Pierre Gasly",
            "Carlos Sainz",
            "Fernando Alonso",
            "Lance Stroll",
        ],
        "QualifyingTime (s)": [
            75.096,
            75.180,
            75.481,
            75.546,
            75.670,
            75.737,
            75.755,
            75.973,
            75.980,
            76.062,
            76.4,
            76.5,
        ],
    })

    driver_mapping = {
        "Lando Norris": "NOR",
        "Oscar Piastri": "PIA",
        "Max Verstappen": "VER",
        "George Russell": "RUS",
        "Yuki Tsunoda": "TSU",
        "Alexander Albon": "ALB",
        "Charles Leclerc": "LEC",
        "Lewis Hamilton": "HAM",
        "Pierre Gasly": "GAS",
        "Carlos Sainz": "SAI",
        "Lance Stroll": "STR",
        "Fernando Alonso": "ALO",
    }

    qualifying_2025["DriverCode"] = qualifying_2025["Driver"].map(driver_mapping)
    merged_data = qualifying_2025.merge(laps_2024, left_on="DriverCode", right_on="Driver")

    X = merged_data[["QualifyingTime (s)"]]
    y = merged_data["LapTime (s)"]
    if X.shape[0] == 0:
        return {"predictions": [], "mae_seconds": None}

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=39)
    model = GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, random_state=39)
    model.fit(X_train, y_train)

    predicted_lap_times = model.predict(qualifying_2025[["QualifyingTime (s)"]])
    qualifying_2025["PredictedRaceTime (s)"] = predicted_lap_times
    ordered = qualifying_2025.sort_values(by="PredictedRaceTime (s)")

    preds = [
        {"driver": row["Driver"], "predicted_seconds": float(row["PredictedRaceTime (s)"])}
        for _, row in ordered.iterrows()
    ]

    y_pred = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, y_pred)) if len(y_test) else None

    return {"predictions": preds, "mae_seconds": mae}


if __name__ == "__main__":
    res = get_monaco_2025_predictions()
    print("\n🏁 Predicted 2025 Monaco GP Winner 🏁\n")
    for p in res["predictions"][:5]:
        print(f"{p['driver']}: {p['predicted_seconds']:.3f}s")
    if res["mae_seconds"] is not None:
        print(f"\n🔍 Model Error (MAE): {res['mae_seconds']:.2f} seconds")