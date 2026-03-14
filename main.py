import socket
import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

def get_local_ip():
    local_ip = "127.0.0.1" # Default fallback
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    return local_ip

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
    port = int(os.environ.get('PORT', 8000))
    return {"ip": get_local_ip(), "port": port}

# The automatic signaling channel
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        if len(manager.active_connections) == 2:
            await manager.broadcast_to_others(json.dumps({"type": "peer_joined"}), websocket)
            
        while True:
            data = await websocket.receive_text()
            await manager.broadcast_to_others(data, websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"Hawkins Network Signaling Server running on port {port}")
    print(f"Access locally at: http://localhost:{port}")
    
    local_ip = get_local_ip()
    if local_ip != "127.0.0.1":
        print(f"Access on network at: http://{local_ip}:{port}")
        
    # Host on 0.0.0.0 so other devices on the LAN can access it
    uvicorn.run(app, host="0.0.0.0", port=port)