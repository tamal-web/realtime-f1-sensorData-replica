import asyncio
import websockets
import json

async def receive_race_data():
    uri = "ws://localhost:8765"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to server")
            while True:
                message = await websocket.recv()
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    print(f"Received non-JSON message: {message}")
                    continue
                print(f"Received data: {data}")
    except websockets.ConnectionClosed:
        print("Connection closed")
    except Exception as e:
        print(f"Client error: {e}")

if __name__ == "__main__":
    asyncio.run(receive_race_data())
