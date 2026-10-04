import socketio
import uvicorn
import collections
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from classifier_service import EyeMovementClassifierService

# =====================================================================
# LỚP HẬU XỬ LÝ (POST-PROCESSING) SMOOTHING TOẠ ĐỘ
# =====================================================================
class EyeCursorController:
    def __init__(self, buffer_size=20, alpha=0.3, debounce_frames=4):
        self.buffer_size = buffer_size
        self.alpha = alpha
        
        # Buffer cố định kích thước cho Fixation
        self.fixation_buffer_x = collections.deque(maxlen=buffer_size)
        self.fixation_buffer_y = collections.deque(maxlen=buffer_size)
        
        # Lưu vết vị trí cuối cùng cho EMA (Smooth Pursuit)
        self.last_ema_x = None
        self.last_ema_y = None
        
        # Lưu lịch sử nhãn để chống nhiễu (Debounce)
        self.debounce_frames = debounce_frames
        self.label_history = collections.deque(maxlen=debounce_frames)
        self.current_stable_label = 0

    def process_coordinates(self, raw_x, raw_y, label):
        """
        Xử lý làm mượt toạ độ dựa trên nhãn ý định của mắt:
        0: Fixation, 1: Smooth Pursuit, 2: Saccade
        """
        # Cập nhật lịch sử nhãn
        self.label_history.append(label)
        
        # Chỉ chuyển trạng thái nếu N frame liên tiếp có cùng một nhãn (tránh chập chờn)
        if len(self.label_history) == self.debounce_frames and len(set(self.label_history)) == 1:
            self.current_stable_label = label
            
        stable_label = self.current_stable_label
        
        if stable_label == 0:  # Fixation: Đang tập trung
            # Lưu tọa độ vào buffer và tính trung bình cộng để chống rung (gaze drift)
            self.fixation_buffer_x.append(raw_x)
            self.fixation_buffer_y.append(raw_y)
            smoothed_x = sum(self.fixation_buffer_x) / len(self.fixation_buffer_x)
            smoothed_y = sum(self.fixation_buffer_y) / len(self.fixation_buffer_y)
            
            # Cập nhật vị trí EMA bằng vị trí trung bình này để nếu chuyển sang 
            # Smooth Pursuit thì có khởi điểm tuyến tính mượt mà.
            self.last_ema_x = smoothed_x
            self.last_ema_y = smoothed_y
            return smoothed_x, smoothed_y
            
        elif stable_label == 1:  # Smooth Pursuit: Đang trượt bám mục tiêu
            # Mắt đang chuyển động mượt, clear ngay lập tức buffer đứng yên
            self.fixation_buffer_x.clear()
            self.fixation_buffer_y.clear()
            
            # Áp dụng bộ lọc Exponential Moving Average (EMA)
            if self.last_ema_x is None or self.last_ema_y is None:
                self.last_ema_x = raw_x
                self.last_ema_y = raw_y
            else:
                self.last_ema_x = self.alpha * raw_x + (1 - self.alpha) * self.last_ema_x
                self.last_ema_y = self.alpha * raw_y + (1 - self.alpha) * self.last_ema_y
            return self.last_ema_x, self.last_ema_y
            
        elif stable_label == 2:  # Saccade: Chuyển hướng nhanh
            # Mắt chớp/nhảy hướng: Vứt bỏ mọi buffer, nhảy tức thời đến tọa độ raw
            self.fixation_buffer_x.clear()
            self.fixation_buffer_y.clear()
            
            # Khởi động lại mốc cho EMA tại điểm đến mới
            self.last_ema_x = raw_x
            self.last_ema_y = raw_y
            return raw_x, raw_y
            
        return raw_x, raw_y

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
client_controllers = {}

WINDOW_SIZE = 30
classifier_service = EyeMovementClassifierService(window_size=WINDOW_SIZE)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Midas Touch 3D Backend is running"}

@app.post("/api/model/save/{sid}")
def save_model(sid: str):
    success = classifier_service.save_participant_model(sid)
    if success:
        return {"status": "ok", "message": "Model saved successfully"}
    else:
        raise HTTPException(status_code=404, detail="Model not found for this session")

@app.post("/api/model/load/{sid}")
def load_model(sid: str):
    success = classifier_service.load_participant_model(sid)
    if success:
        return {"status": "ok", "message": "Model loaded successfully"}
    else:
        raise HTTPException(status_code=404, detail="Saved model not found or failed to load")

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")
    client_buffers[sid] = []
    client_controllers[sid] = EyeCursorController(buffer_size=20, alpha=0.3, debounce_frames=4)
    await sio.emit("connection_ack", {"status": "connected", "sid": sid}, room=sid)

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    if sid in client_buffers:
        del client_buffers[sid]
    if sid in client_controllers:
        del client_controllers[sid]
    classifier_service.cleanup_participant(sid)

@sio.event
async def gaze_data(sid, data):
    if sid not in client_buffers:
        client_buffers[sid] = []
        client_controllers[sid] = EyeCursorController(buffer_size=20, alpha=0.3, debounce_frames=4)
        
    buffer = client_buffers[sid]
    buffer.append(data)
    
    if len(buffer) > WINDOW_SIZE:
        buffer.pop(0)
        
    # Bước 1: Trích xuất nhãn hành vi từ Hierarchical GMM-HMM
    predicted_label = classifier_service.predict(buffer, sid=sid)
    label_names = {0: "Fixation", 1: "Smooth Pursuit", 2: "Saccade"}
    
    raw_x = data.get("x", 0.0)
    raw_y = data.get("y", 0.0)
    
    # Bước 2: Hậu xử lý toạ độ (Coordinate Smoothing)
    controller = client_controllers[sid]
    smoothed_x, smoothed_y = controller.process_coordinates(raw_x, raw_y, predicted_label)
    
    # Bước 3: Trả toạ độ đã làm mượt (x, y) về cho Frontend
    await sio.emit("gaze_result", {
        "x": smoothed_x,
        "y": smoothed_y,
        "raw_x": raw_x,
        "raw_y": raw_y,
        "v": data.get("v", 0.0),
        "label": predicted_label,
        "label_name": label_names[predicted_label],
        "buffer_size": len(buffer)
    }, room=sid)

if __name__ == "__main__":
    uvicorn.run("main:socket_app", host="127.0.0.1", port=8001, reload=True)
