# MIDAS Touch 3D

MIDAS Touch 3D là hệ thống mô phỏng huấn luyện phẫu thuật tương tác bằng ánh nhìn. Frontend hiển thị scene 3D và gửi dữ liệu gaze; backend nhận dữ liệu thời gian thực, phân loại chuyển động mắt bằng GMM-HMM, làm mượt tọa độ và trả kết quả về frontend.

## Tính năng

- Hiển thị và tương tác scene 3D bằng Next.js, React Three Fiber và Three.js.
- Nhận gaze data qua Socket.IO/WebSocket.
- Phân loại ba trạng thái:
  - `0`: Fixation
  - `1`: Smooth Pursuit
  - `2`: Saccade
- GMM-HMM phân cấp: tầng 1 phân đoạn `(x, y)`, tầng 2 phân loại vận tốc `v`.
- Fallback theo ngưỡng vận tốc khi chưa có model participant.
- Làm mượt tọa độ theo nhãn và debounce trạng thái.
- Huấn luyện, lưu và tải model riêng cho từng session/participant.

## Cấu trúc project

```text
midas/
├── midas_touch_3d_frontend/       # Next.js + React + Three.js
│   ├── app/
│   ├── components/
│   ├── store/
│   └── package.json
├── midas_touch_3d_backend/        # FastAPI + Socket.IO + GMM-HMM
│   ├── main.py
│   ├── classifier_service.py
│   ├── notebook_classifier.py
│   ├── gaze_filter.py
│   └── requirements.txt
├── Cac_Httm/                     # Mã nghiên cứu và thử nghiệm GMM-HMM
├── *.ipynb                       # Notebook huấn luyện/đánh giá
├── *.py                          # Script xử lý eye movement
└── *.pdf                         # Tài liệu và paper tham khảo
```

Xem hướng dẫn riêng cho phần GMM-HMM tại [Cac_Httm/README.md](./Cac_Httm/README.md).

## Yêu cầu

- Node.js 18 trở lên.
- Python 3.10 trở lên.
- npm.
- Webcam hoặc thiết bị eye tracking tương thích.

Project chạy local không bắt buộc PostgreSQL, Redis hoặc Docker. Backend hiện lưu trạng thái client trong bộ nhớ và lưu model participant ra file khi được yêu cầu.

## Cài đặt

### Backend

```powershell
cd midas_touch_3d_backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Frontend

Mở terminal khác:

```powershell
cd midas_touch_3d_frontend
npm install
```

## Chạy ứng dụng

### Backend

Từ `midas_touch_3d_backend/`:

```powershell
python -m uvicorn main:socket_app --reload --host 127.0.0.1 --port 8001
```

Kiểm tra:

```text
http://127.0.0.1:8001/
```

Kết quả mong đợi:

```json
{"status":"ok","message":"Midas Touch 3D Backend is running"}
```

### Frontend

Từ `midas_touch_3d_frontend/`:

```powershell
npm run dev
```

Mở `http://localhost:3000`.

Frontend mặc định kết nối tới `http://127.0.0.1:8001`. Có thể thay đổi:

```powershell
$env:NEXT_PUBLIC_SOCKET_URL = "http://127.0.0.1:8001"
npm run dev
```

## API backend

```text
GET  /
POST /api/model/save/{sid}
POST /api/model/load/{sid}
```

Model mặc định được lưu/tải từ `saved_eye_model.pkl` theo working directory của backend.

## Socket.IO events

### Client gửi `gaze_data`

```json
{
  "x": 0.5,
  "y": 0.5,
  "v": 0.02,
  "nx": 0.1,
  "ny": -0.2,
  "timestamp": 1710000000000
}
```

### Backend trả `gaze_result`

```json
{
  "x": 0.5,
  "y": 0.5,
  "raw_x": 0.5,
  "raw_y": 0.5,
  "v": 0.02,
  "label": 1,
  "label_name": "Smooth Pursuit",
  "sx": 0.1,
  "sy": -0.2,
  "buffer_size": 30
}
```

## Pipeline GMM-HMM

1. Frontend gửi tọa độ và vận tốc.
2. Backend giữ cửa sổ tối đa 30 mẫu.
3. Khi chưa có model participant, backend dùng fallback theo `v`.
4. Sau khoảng 600 mẫu, backend khởi tạo model participant.
5. `NotebookClassifier` chạy GMM-HMM phân cấp.
6. Nhãn được debounce để giảm nhiễu.
7. Tọa độ được làm mượt theo nhãn.
8. Backend trả dữ liệu đã xử lý về frontend.

Ngưỡng fallback hiện tại:

| Vận tốc | Nhãn |
|---:|---|
| `v <= 0.01` | Fixation |
| `0.01 < v <= 0.05` | Smooth Pursuit |
| `v > 0.05` | Saccade |

## Chạy mã trong `Cac_Httm`

```powershell
cd Cac_Httm
python -m pip install numpy pandas scipy scikit-learn hmmlearn matplotlib jupyter
python GMM_HMM_layer1.py
python GMM_HMM_full_layer.py
```

Mở notebook:

```powershell
jupyter notebook
```

Các file nghiên cứu chính:

- `GMM_HMM_layer1.py`: Step 0 và GMM-HMM tầng 1.
- `GMM_HMM_full_layer.py`: pipeline hai tầng.
- `GMM_HMM_full_layer_eval.ipynb`: đánh giá pipeline.
- `baseline_one_gmmhmm_overlap.ipynb`: baseline một GMM-HMM.

Chi tiết tùy chọn command line và định dạng dữ liệu nằm trong [Cac_Httm/README.md](./Cac_Httm/README.md).

## Build frontend

```powershell
cd midas_touch_3d_frontend
npm run build
npm run start
```

## Xử lý lỗi thường gặp

- **Không kết nối backend:** kiểm tra port `8001` và `NEXT_PUBLIC_SOCKET_URL`.
- **Chưa có model participant:** session mới sẽ dùng fallback và tự thu thập mẫu.
- **GMM-HMM không hội tụ:** kiểm tra số mẫu, thử giảm `n_mix`, tăng `n_iter` hoặc dùng khởi tạo K-means.
- **Notebook lỗi thư viện:** kích hoạt đúng virtual environment rồi cài các package trong phần Cài đặt.

## Tài liệu

- [Hướng dẫn tích hợp gaze filter](./midas_touch_3d_backend/GAZE_PATCH_GUIDE.md)
- [README GMM-HMM](./Cac_Httm/README.md)
- Các paper và notebook trong thư mục gốc.

## License

Project private phục vụ nghiên cứu và phát triển. Việc sử dụng, phân phối và triển khai cần tuân theo thỏa thuận của nhóm phát triển.
