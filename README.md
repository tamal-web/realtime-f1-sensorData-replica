# F1 Telemetry WebSocket Server — README

A WebSocket server that replays historical Formula 1 telemetry as a **real-time race simulator** and emits prediction payloads for strategy decisions (best pit stops, tyre compound sequences, overtaking probability, etc.). It is intended as a prototype real‑time prediction API that receives live-like sensor streams from cars and runs prediction models on top of that stream.

> **Short project description:**
>
> This project implements a WebSocket API that simulates a real-time sensor feed for an F1 race. The server replays historical telemetry as if it were live sensor data so downstream apps can run prediction algorithms (for example: best pit-stop timing, tyre compound sequencing, and overtaking probability). We do not yet have real live sensor feeds from cars — instead we built a faithful replica from previous race telemetry and stream it at 50 Hz (50 samples per second) to approximate real-time behavior without the overhead of 1000 Hz used in some real systems. In short: it’s a WebSocket API to _experience old races in real live time_ and test real-time prediction models.

---

# Features

- Loads a FastF1 session (configurable) and streams per-driver telemetry over a WebSocket connection (`ws://localhost:8765`).
- Sends a one-time prediction payload using `ai.predict.get_monaco_2025_predictions(...)` when a client connects.
- Uses a FastF1 cache to avoid repeated downloads of telemetry.
- Replays telemetry as a simulated live feed (50 Hz by design in the prototype) so prediction models can consume and react to data.

---

# Table of contents

- [Prerequisites](#prerequisites)
- [Project layout](#project-layout)
- [Installation](#installation)
- [requirements.txt (example)](#requirementstxt-example)
- [Configuration notes](#configuration-notes)
- [Running the server locally](#running-the-server-locally)
- [Client examples](#client-examples)
- [Troubleshooting](#troubleshooting)
- [Extending / Developer notes](#extending--developer-notes)
- [License](#license)

---

# Prerequisites

- **Python 3.9+** (3.10 or 3.11 recommended)
- Internet access to download FastF1 session data the first time (cache avoids repeat downloads)
- Familiarity with virtual environments (recommended)

---

# Project layout (recommended)

```
.
├── server/main.py                 # main server script (run with `python server/main.py`)
├── backend/
│   └── ai/
│       └── predict.py        # must provide get_monaco_2025_predictions(cache_dir: str)
├── cache/                    # fastf1 cache (created automatically)
├── requirements.txt
└── README.md
```

The script contains a fallback that appends a parent backend root to `sys.path` so `ai.predict` can be imported when running from the repository root. For stable imports, package `ai` or run from the repository root.

---

# Installation

1. Clone the repository and `cd` into it:

```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

3. Upgrade pip and install dependencies:

```bash
python -m pip install --upgrade pip wheel
pip install -r requirements.txt
```

If you don't have a `requirements.txt` yet, install manually:

```bash
pip install fastf1 pandas websockets numpy scipy matplotlib
```

---

# `requirements.txt` (example)

```
fastf1
pandas
websockets
numpy
scipy
matplotlib
# Add model dependencies if needed, e.g.:
# scikit-learn
# torch
```

---

# Configuration notes

- **FastF1 cache**: The server enables FastF1 caching to reduce repeated downloads. The script determines a relative `cache/` folder — you can change this path inside `server/main.py` if desired.

- **Replica sensor data & frequency**: Because we don't have actual live car sensors, the server **replays historical telemetry** pulled via FastF1 and emits it as a simulated sensor stream. The prototype streams at **50 Hz** (50 messages per second) rather than 1,000 Hz to balance realism and resource usage. This sampling rate is sufficient for prototype prediction models (pit strategy, tyre sequencing, overtaking probability) while avoiding the heavy I/O and CPU costs of very high-frequency streams.

- **Importing `ai.predict`**: If `ai.predict` import fails, run the server from the repository root or make `ai` installable (`pip install -e .`) so the module is importable from any working directory.

---

# Running the server locally

Activate your virtualenv (if not already):

```bash
source .venv/bin/activate
```

Run the server:

```bash
python server/main.py
```

Expected log output:

```
INFO:root:WebSocket server started on ws://localhost:8765
```

The server listens on `localhost:8765` and streams telemetry messages to connected clients. Press `Ctrl+C` to stop the server — it will perform a graceful shutdown.

---

# Client examples

## JavaScript (browser or Node)

```js
const ws = new WebSocket("ws://localhost:8765");

ws.addEventListener("open", () => {
  console.log("Connected");
});

ws.addEventListener("message", (evt) => {
  const data = JSON.parse(evt.data);
  console.log("Message:", data);
});

ws.addEventListener("close", () => {
  console.log("Connection closed");
});
```

## Python (test client)

```python
import asyncio
import websockets
import json

async def client():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        while True:
            msg = await websocket.recv()
            data = json.loads(msg)
            print(data)

asyncio.run(client())
```

## CLI (wscat)

```bash
npm i -g wscat
wscat -c ws://localhost:8765
```

---

# Troubleshooting / common errors

**No module named 'fastf1'**

- Activate the virtualenv and `pip install fastf1`.

**No module named 'ai.predict'**

- Run the server from the repository root where `backend/` exists.
- Or make `ai` an installable package and `pip install -e .`.
- Alternatively export `PYTHONPATH` to include your backend directory:

  ```bash
  export PYTHONPATH="$PWD/backend:$PYTHONPATH"
  python server/main.py
  ```

**FastF1 fails to download data / times out**

- Ensure your network connection is working.
- Verify the event name/year/session are valid in FastF1 (change the `get_session` parameters if needed).

---

# Extending / Developer notes

- The server currently round-robins telemetry rows between drivers and sends messages with a short `await asyncio.sleep(0.002)` — you can tune the sleep/delay logic and message batching to control the effective message rate. In the prototype we intentionally target ~50 updates per second aggregate to approximate real-time behavior.
- Add CLI flags (`argparse`) to select `--year`, `--event`, `--session`, `--port`, and `--hz`.
- Add TLS & authentication for production use.
- Containerize with a Dockerfile for easy deployment.

---

# Example `backend/ai/predict.py` stub

```python
def get_monaco_2025_predictions(cache_dir: str):
    # Return a JSON-serializable object (dict/list)
    return {
        "pred_version": "stub-0.1",
        "created_at": "2025-11-16T00:00:00Z",
        "predictions": [
            {"driver": "VER", "position": 1},
            {"driver": "LEC", "position": 2}
        ]
    }
```

---

# Quick checklist before opening an issue

- [ ] Virtualenv activated
- [ ] `pip install -r requirements.txt` completed
- [ ] `ai.predict.get_monaco_2025_predictions` is present and importable
- [ ] Network access available for FastF1 downloads (or cached data present)
- [ ] Running from repository root (if relying on relative imports)

---

# Contributing

Open issues / PRs for packaging `ai`, adding CLI options, Dockerfile, or tests.

---

# License

MIT — add a `LICENSE` file if desired.

---

If you want, I can also:

- Generate a pinned `requirements.txt`.
- Add an `argparse` wrapper to `server/main.py` with `--year`, `--event`, `--session`, `--port`, and `--hz`.
- Create a Dockerfile and a systemd unit file for background runs.

Which would you like next?
