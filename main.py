import socket
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
import json
import os

app = FastAPI()

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Best method: Forces the OS to find the interface used for actual network routing
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            # Fallback for completely offline LANs/Hotspots without internet access
            s.connect(('192.168.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip

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
        # Send the WebRTC tokens to the *other* connected laptop/device
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
    
@app.get("/get-ip")
async def get_ip():
    return {"ip": get_local_ip(), "port": 8000}

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