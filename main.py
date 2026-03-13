from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
import json
import os

app = FastAPI()

# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_to_others(self, message: str, sender: WebSocket):
        # Send the WebRTC tokens to the *other* connected laptop
        for connection in self.active_connections:
            if connection != sender:
                await connection.send_text(message)

manager = ConnectionManager()

# Serve the static HTML frontend
@app.get("/")
async def get_frontend():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# The automatic signaling channel
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # If a second person joins, tell the first person to initiate the connection automatically
        if len(manager.active_connections) == 2:
            await manager.broadcast_to_others(json.dumps({"type": "peer_joined"}), websocket)
            
        while True:
            # Listen for WebRTC data and pass it to the other laptop
            data = await websocket.receive_text()
            await manager.broadcast_to_others(data, websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    # Host on 0.0.0.0 so other devices on the hotspot/Wi-Fi can access it
    uvicorn.run(app, host="0.0.0.0", port=8000)