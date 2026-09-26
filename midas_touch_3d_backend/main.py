import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from classifier_service import EyeMovementClassifierService

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = FastAPI(title="Midas Touch 3D Simulator Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_app = socketio.ASGIApp(sio, app)

client_buffers = {}
WINDOW_SIZE = 30

classifier_service = EyeMovementClassifierService(window_size=WINDOW_SIZE)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Midas Touch 3D Backend is running"}

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")
    client_buffers[sid] = []
    await sio.emit("connection_ack", {"status": "connected", "sid": sid}, room=sid)

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    if sid in client_buffers:
        del client_buffers[sid]

@sio.event
async def gaze_data(sid, data):
    if sid not in client_buffers:
        client_buffers[sid] = []
        
    buffer = client_buffers[sid]
    buffer.append(data)
    
    if len(buffer) > WINDOW_SIZE:
        buffer.pop(0)
        
    # Bước 2: Tích hợp GMM-HMM Classifier
    predicted_label = classifier_service.predict(buffer)
    label_names = {0: "Fixation", 1: "Smooth Pursuit", 2: "Saccade"}
    
    await sio.emit("gaze_result", {
        "x": data.get("x", 0.0),
        "y": data.get("y", 0.0),
        "v": data.get("v", 0.0),
        "label": predicted_label,
        "label_name": label_names[predicted_label],
        "buffer_size": len(buffer)
    }, room=sid)

if __name__ == "__main__":
    uvicorn.run("main:socket_app", host="127.0.0.1", port=8001, reload=True)
