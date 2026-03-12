const ws = new WebSocket(`ws://${window.location.host}/ws`);
const config = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };
const pc = new RTCPeerConnection(config);

let dataChannel;

// UI Elements
const chatBox = document.getElementById('chatBox');
const msgInput = document.getElementById('msgInput');
const sendBtn = document.getElementById('sendBtn');
const startBtn = document.getElementById('startBtn');

function appendMessage(sender, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;
    msgDiv.innerText = text;
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Helper to configure the data channel once it's created or received
function setupDataChannel(channel) {
    channel.onopen = () => {
        appendMessage('system', 'P2P Connection Established!');
        msgInput.disabled = false;
        sendBtn.disabled = false;
        startBtn.disabled = true;
    };
    channel.onmessage = (event) => {
        appendMessage('them', `Peer: ${event.data}`);
    };
    channel.onclose = () => {
        appendMessage('system', 'Peer disconnected.');
    };
}

// 1. If YOU click "Start", you are the Caller. You create the Data Channel and the Offer.
startBtn.onclick = async () => {
    startBtn.disabled = true;
    dataChannel = pc.createDataChannel('chat');
    setupDataChannel(dataChannel);

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    ws.send(JSON.stringify({ type: 'offer', sdp: pc.localDescription.sdp }));
};

// 2. If you are the Receiver, the data channel arrives automatically through the PeerConnection.
pc.ondatachannel = (event) => {
    dataChannel = event.channel;
    setupDataChannel(dataChannel);
};

// 3. Send ICE candidates to the other peer instantly as the browser finds them
pc.onicecandidate = (event) => {
    if (event.candidate) {
        ws.send(JSON.stringify({ type: 'candidate', candidate: event.candidate }));
    }
};

// 4. Handle signaling messages from the WebSocket (Offers, Answers, and Candidates)
ws.onmessage = async (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'offer') {
        startBtn.disabled = true; // Hide start button for the receiver
        await pc.setRemoteDescription(new RTCSessionDescription(message));
        
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        ws.send(JSON.stringify({ type: 'answer', sdp: pc.localDescription.sdp }));
    } 
    else if (message.type === 'answer') {
        await pc.setRemoteDescription(new RTCSessionDescription(message));
    } 
    else if (message.type === 'candidate') {
        await pc.addIceCandidate(new RTCIceCandidate(message.candidate));
    }
};

// 5. Send chat messages over the P2P connection
function sendMessage() {
    const text = msgInput.value.trim();
    if (text && dataChannel && dataChannel.readyState === 'open') {
        dataChannel.send(text);
        appendMessage('me', `You: ${text}`);
        msgInput.value = '';
    }
}

sendBtn.onclick = sendMessage;
msgInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});