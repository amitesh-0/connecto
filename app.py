import socketio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import random

# Initialize Socket.IO and FastAPI
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()

# Mount the static folder for the HTML file
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# Wrap FastAPI with Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# Dictionary to keep track of connected devices
connected_users = {}
adjectives = ["Fast", "Cool", "Brave", "Sneaky", "Happy", "Wild"]
animals = ["Fox", "Bear", "Hawk", "Tiger", "Wolf", "Owl"]

async def broadcast_peers():
    """Sends the updated list of available devices to everyone"""
    peer_list = [{"id": sid, "name": name} for sid, name in connected_users.items()]
    await sio.emit('update_peers', peer_list)

@sio.event
async def connect(sid, environ):
    # Assign a random display name to the new device
    device_name = f"{random.choice(adjectives)} {random.choice(animals)}"
    connected_users[sid] = device_name
    print(f"Device connected: {device_name} ({sid})")
    
    # Tell everyone the list of peers has updated
    await broadcast_peers()
    # Tell the user what their own ID is so they don't see themselves in the list
    await sio.emit('your_id', sid, room=sid)

@sio.event
async def disconnect(sid):
    if sid in connected_users:
        print(f"Device disconnected: {connected_users[sid]}")
        del connected_users[sid]
        await broadcast_peers()

@sio.event
async def webrtc_signal(sid, data):
    """Relays WebRTC offers, answers, and ICE candidates to the specific target"""
    target_id = data.get('target')
    if target_id in connected_users:
        await sio.emit('webrtc_signal', {
            'sender_id': sid,
            'sender_name': connected_users[sid],
            'signal': data.get('signal')
        }, room=target_id)