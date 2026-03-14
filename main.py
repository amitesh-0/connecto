import os
import socket
import json
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import socketio
import uvicorn
from zeroconf import ServiceInfo, Zeroconf

# Create FastAPI app
app = FastAPI()

# Create SocketIO server (replaces raw WebSockets for better event handling & rooms)
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

# State management
devices = {}
sessions = {}

# Cache local IP
_local_ip = None

def get_local_ip():
    global _local_ip
    if _local_ip:
        return _local_ip
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        _local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        _local_ip = "127.0.0.1"
    return _local_ip

# Combine IP endpoints to maintain main.py functionality
@app.get("/get-ip")
async def get_ip():
    port = int(os.environ.get('PORT', 8000))
    return JSONResponse({"ip": get_local_ip(), "port": port})

# Serve the static HTML frontend
@app.get("/")
async def get_frontend():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# Mount static files just in case you add CSS/JS assets
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static_assets")
app.mount("/", StaticFiles(directory=os.path.dirname(__file__), html=True), name="static")

# Mount SocketIO server to FastAPI
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# --- SocketIO Events ---

@sio.event
async def connect(sid, environ, *args, **kwargs):
    print('A user connected:', sid)

@sio.event
async def register_device(sid, data):
    devices[sid] = {
        'id': sid,
        'name': data.get('name'),
        'type': data.get('type')
    }
    print(f"Device registered: {data.get('name')} ({data.get('type')})")
    await sio.emit('device_list', list(devices.values()))

@sio.event
async def join_session(sid, data):
    session_id = data.get('sessionId')
    if not session_id:
        await sio.emit('session_error', {'message': 'Invalid session ID'}, to=sid)
        return

    peers = sessions.get(session_id, [])

    if len(peers) >= 2:
        await sio.emit('session_full', {'sessionId': session_id}, to=sid)
        return

    if sid not in peers:
        peers.append(sid)
    sessions[session_id] = peers
    await sio.enter_room(sid, session_id)

    print(f"[Session {session_id[:8]}] Peer joined: {sid} ({len(peers)}/2)")

    if len(peers) == 2:
        await sio.emit('session_ready', {'sessionId': session_id, 'isInitiator': True, 'peerId': peers[1]}, to=peers[0])
        await sio.emit('session_ready', {'sessionId': session_id, 'isInitiator': False, 'peerId': peers[0]}, to=peers[1])

@sio.event
async def connection_request(sid, data):
    target = data.get('target')
    print(f"Connection request from {devices.get(sid, {}).get('name')} to {target}")
    await sio.emit('connection_request', {
        'sender': sid,
        'senderName': devices.get(sid, {}).get('name'),
        'senderType': devices.get(sid, {}).get('type')
    }, to=target)

@sio.event
async def connection_response(sid, data):
    target = data.get('target')
    accepted = data.get('accepted')
    print(f"Connection response from {sid} to {target}: {'Accepted' if accepted else 'Rejected'}")
    await sio.emit('connection_response', {'responder': sid, 'accepted': accepted}, to=target)

@sio.event
async def offer(sid, data):
    target = data.get('target')
    session_id = data.get('sessionId')
    payload = {'sender': sid, 'sdp': data.get('sdp')}
    if session_id:
        await sio.emit('offer', payload, room=session_id, skip_sid=sid)
    elif target:
        await sio.emit('offer', payload, to=target)

@sio.event
async def answer(sid, data):
    target = data.get('target')
    session_id = data.get('sessionId')
    payload = {'sender': sid, 'sdp': data.get('sdp')}
    if session_id:
        await sio.emit('answer', payload, room=session_id, skip_sid=sid)
    elif target:
        await sio.emit('answer', payload, to=target)

@sio.event
async def ice_candidate(sid, data):
    target = data.get('target')
    session_id = data.get('sessionId')
    payload = {'sender': sid, 'candidate': data.get('candidate')}
    if session_id:
        await sio.emit('ice_candidate', payload, room=session_id, skip_sid=sid)
    elif target:
        await sio.emit('ice_candidate', payload, to=target)

@sio.event
async def disconnect(sid):
    print('User disconnected:', sid)
    if sid in devices:
        print(f"Device removed: {devices[sid].get('name')}")
        del devices[sid]
        await sio.emit('device_list', list(devices.values()))

    for session_id in list(sessions.keys()):
        if sid in sessions[session_id]:
            sessions[session_id].remove(sid)
            if not sessions[session_id]:
                del sessions[session_id]
                print(f"[Session {session_id[:8]}] Session ended (empty)")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"Hawkins Network Signaling Server running on port {port}")
    print(f"Access locally at: http://localhost:{port}")
    
    local_ip = get_local_ip()
    if local_ip != "127.0.0.1":
        print(f"Access on network at: http://{local_ip}:{port}")
        
    # --- mDNS SETUP ---
    # Tweaked to match the "Hawkins" branding from your original file
    info = ServiceInfo(
        "_hawkins._tcp.local.",
        "Hawkins Signaling Server._hawkins._tcp.local.",
        addresses=[socket.inet_aton(local_ip)],
        port=port,
        properties={'description': 'Hawkins Local Signaling Server', 'name': 'Hawkins'},
        server="hawkins.local."
    )
    
    zeroconf = Zeroconf()
    print("Registering mDNS service...")
    zeroconf.register_service(info)
    
    try:
        uvicorn.run(socket_app, host="0.0.0.0", port=port)
    finally:
        print("Unregistering mDNS service...")
        zeroconf.unregister_service(info)
        zeroconf.close()