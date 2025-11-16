import asyncio
import json
import logging
from pathlib import Path
import pandas as pd
import fastf1
try:
    from ai.predict import get_monaco_2025_predictions
except Exception:
    import sys as _sys
    from pathlib import Path as _Path
    # Ensure backend root is on sys.path so 'ai' can be imported without a package
    _backend_root = _Path(__file__).resolve().parents[1]
    if str(_backend_root) not in _sys.path:
        _sys.path.append(str(_backend_root))
    from ai.predict import get_monaco_2025_predictions
import websockets
from datetime import datetime

# Configure logging to see server activity
logging.basicConfig(level=logging.INFO)

async def broadcast_race_data(*args):
    """
    Fetches historical F1 race data using fastf1 and broadcasts it over a WebSocket connection,
    simulating a real-time data feed.
    """
    websocket = args[0]
    logging.info(f"Client connected from {websocket.remote_address}")
    try:
        # Send a small message immediately to confirm connection
        await websocket.send(json.dumps({"type": "info", "message": "connected"}))
        # Ensure FastF1 cache is enabled to avoid repeated downloads and reduce failures
        cache_dir = Path(__file__).resolve().parents[2] / "cache"
        fastf1.Cache.enable_cache(str(cache_dir))
        try:
            # Load data for a specific race session.
            # For example, the 2023 Japanese Grand Prix Race ('R').
            # You can change the year, event name, and session type ('FP1', 'FP2', 'FP3', 'Q', 'R').
            session = fastf1.get_session(2023, 'Monaco', 'R')
            session.load(telemetry=True)
            logging.info("F1 session data loaded successfully.")

            # Send one-time Monaco 2025 predictions (historical-based)
            try:
                preds = get_monaco_2025_predictions(str(cache_dir))
                await websocket.send(json.dumps({
                    "type": "prediction",
                    "data": preds
                }))
            except Exception as pred_err:
                logging.warning(f"Prediction sending failed: {pred_err}")

            # Stream telemetry for all drivers in the session
            driver_codes = session.laps["Driver"].unique().tolist()
            logging.info(f"Streaming telemetry for {len(driver_codes)} drivers")

            cumulative_km_map: dict[str, float] = {code: 0.0 for code in driver_codes}
            # Track live lap number and distance covered within current lap for ranking
            current_lap_map: dict[str, int | None] = {code: None for code in driver_codes}
            lap_km_map: dict[str, float] = {code: 0.0 for code in driver_codes}

            # Build per-driver concatenated car_data with lap metadata
            driver_streams: dict[str, pd.DataFrame] = {}
            for driver_code in driver_codes:
                d_laps = session.laps.pick_driver(driver_code)
                parts = []
                for _, lap in d_laps.iterlaps():
                    car_data = None
                    try:
                        car_data = lap.get_car_data()
                    except Exception:
                        car_data = None
                    if car_data is None or car_data.empty:
                        continue
                    df = car_data.copy()
                    df["__LapNumber"] = int(lap["LapNumber"]) if "LapNumber" in lap else None
                    df["__Position"] = int(lap["Position"]) if ("Position" in lap and not pd.isna(lap["Position"])) else None
                    parts.append(df)
                if parts:
                    stream = pd.concat(parts, ignore_index=True)
                    # Ensure time column exists for dt calc
                    if "Time" in stream:
                        times = stream["Time"].astype("timedelta64[ns]")
                    else:
                        times = stream.index.astype("timedelta64[ns]")
                    stream["__dt_sec"] = pd.Series(times).diff().dt.total_seconds().fillna(0.0)
                    driver_streams[driver_code] = stream

            # Round-robin over drivers to interleave events
            indices: dict[str, int] = {code: 0 for code in driver_streams.keys()}
            remaining = True
            while remaining:
                remaining = False
                for driver_code, stream in driver_streams.items():
                    i = indices[driver_code]
                    if i >= len(stream):
                        continue
                    remaining = True
                    row = stream.iloc[i]
                    indices[driver_code] = i + 1

                    speed = float(row["Speed"]) if "Speed" in row and row["Speed"] is not None else 0.0
                    dt = float(row["__dt_sec"]) if "__dt_sec" in row else 0.0
                    delta_km = (speed * dt) / 3600.0
                    cumulative_km_map[driver_code] += delta_km

                    # Update live lap tracking
                    lap_num = int(row["__LapNumber"]) if not pd.isna(row["__LapNumber"]) else None
                    prev_lap = current_lap_map.get(driver_code)
                    if lap_num is not None:
                        if prev_lap is None or lap_num > prev_lap:
                            # New lap started; reset in-lap distance
                            current_lap_map[driver_code] = lap_num
                            lap_km_map[driver_code] = 0.0
                        # accumulate in-lap distance
                        lap_km_map[driver_code] += delta_km

                    # Compute live ranks across drivers present
                    ranking_pool = []
                    for dc in driver_codes:
                        ln = current_lap_map.get(dc)
                        if ln is None:
                            continue
                        ranking_pool.append((dc, ln, lap_km_map.get(dc, 0.0)))
                    ranking_pool.sort(key=lambda t: (-t[1], -t[2]))  # lap desc, in-lap km desc
                    live_rank_map = {dc: idx + 1 for idx, (dc, _, __) in enumerate(ranking_pool)}

                    out = {
                        "type": "telemetry",
                        "driver": str(driver_code),
                        "lap_number": int(row["__LapNumber"]) if not pd.isna(row["__LapNumber"]) else None,
                        # Emit live rank (position) based on current lap and in-lap progress
                        "position": live_rank_map.get(driver_code),
                        "position_from_start_km": cumulative_km_map[driver_code],
                        "speed_kmh": speed,
                    }
                    await websocket.send(json.dumps(out))
                    await asyncio.sleep(0.002)
        except Exception as e:
            logging.error(f"FastF1 data pipeline failed: {e}")
            try:
                await websocket.send(json.dumps({"type": "error", "message": str(e)}))
            except Exception:
                pass

    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        logging.info(f"Client disconnected from {websocket.remote_address}")

async def main():
    """
    Starts the WebSocket server on localhost at port 8765.
    """
    # Create and start the WebSocket server.
    async with websockets.serve(broadcast_race_data, "localhost", 8765):
        logging.info("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        # Run the main function to start the server.
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C.
        logging.info("Server shutting down.")

