# Hướng dẫn tích hợp: mắt đỡ phải "banh", tracking mượt hơn

Copy `gaze_filter.py` vào `midas_touch_3d_backend/`, rồi áp dụng 3 phần dưới.

---

## 1. Backend — `main.py`

```python
from gaze_filter import GazeSmoother

client_smoothers = {}   # thêm cạnh client_controllers
```

Trong `connect`:
```python
client_smoothers[sid] = GazeSmoother()
```

Trong `disconnect`:
```python
client_smoothers.pop(sid, None)
```

Thay phần cuối của `gaze_data` (từ sau `process_coordinates`):

```python
    smoothed_x, smoothed_y = controller.process_coordinates(raw_x, raw_y, predicted_label)
    stable_label = controller.current_stable_label     # nhãn ĐÃ debounce

    # Làm mượt gaze màn hình (NDC) -> frontend dùng cái này để bắn tia
    sm = client_smoothers.setdefault(sid, GazeSmoother())
    ts = data.get("timestamp", 0.0) / 1000.0
    sx, sy = sm.process(data.get("nx"), data.get("ny"), ts, stable_label)

    await sio.emit("gaze_result", {
        "x": smoothed_x, "y": smoothed_y,
        "raw_x": raw_x, "raw_y": raw_y,
        "v": data.get("v", 0.0),
        "label": stable_label,                         # <-- trước đây gửi predicted_label
        "label_name": label_names[stable_label],
        "sx": sx, "sy": sy,
        "buffer_size": len(buffer),
    }, room=sid)
```

Hai event cho bước hiệu chỉnh đa thức (tuỳ chọn, xem mục 3):

```python
@sio.event
async def calib_add(sid, data):
    client_smoothers.setdefault(sid, GazeSmoother()).calib.add_sample(data["raw"], data["target"])

@sio.event
async def calib_fit(sid, data=None):
    ok = client_smoothers.setdefault(sid, GazeSmoother()).calib.fit()
    await sio.emit("calib_result", {"ok": ok}, room=sid)
```

---

## 2. Frontend

### 2a. `store/useGazeStore.ts`
Thêm vào interface `GazeState`: `filteredGaze: { x: number; y: number } | null;`
Và trong `create(...)`: `filteredGaze: null,`

### 2b. `components/OverlayUI.tsx`
Lấy thêm `filteredGaze` từ store, và crosshair dùng nó:

```tsx
const g = filteredGaze ?? screenGaze;
style={isWebcamMode
  ? { left: `${(g.x + 1) * 50}%`, top: `${(-g.y + 1) * 50}%` }
  : { left: '50%', top: '50%' }}
```

### 2c. `components/Scene3D.tsx` — thay toàn bộ `GazeController`

```tsx
import { useMemo } from 'react'; // thêm vào import react

const SNAP_RADIUS = 0.09;   // NDC: nhìn gần vật trong bán kính này vẫn tính là trúng
const GRACE_MS = 300;       // lỡ trượt khỏi vật < 300ms thì KHÔNG mất tiến độ
const DWELL_MS = 800;

const GazeController = () => {
  const { camera, scene } = useThree();
  const socketRef = useRef<Socket | null>(null);
  const raycaster = useMemo(() => new THREE.Raycaster(), []);
  const lastPosRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const lastRawRef = useRef<{ x: number; y: number } | null>(null);
  const filteredRef = useRef<{ x: number; y: number } | null>(null);
  const dwellRef = useRef<{ id: string | null; ms: number; lastSeen: number }>({ id: null, ms: 0, lastSeen: 0 });

  useEffect(() => {
    const socket = io(SOCKET_URL, { transports: ['websocket', 'polling'], reconnectionAttempts: 10 });
    socketRef.current = socket;
    const st = useGazeStore.getState();
    socket.on('connect', () => { st.setConnected(true); st.setSocketId(socket.id || null); });
    socket.on('disconnect', () => { st.setConnected(false); st.setSocketId(null); });
    socket.on('gaze_result', (d) => {
      useGazeStore.getState().setGazeData(d.x, d.y, d.v, d.label, d.label_name);
      if (d.sx != null && d.sy != null) {
        filteredRef.current = { x: d.sx, y: d.sy };
        useGazeStore.setState({ filteredGaze: { x: d.sx, y: d.sy } });
      }
    });
    return () => { socket.disconnect(); };
  }, []);

  useFrame((_, delta) => {
    const s = useGazeStore.getState();
    const rayNdc = new THREE.Vector2(0, 0);
    let newRaw: { x: number; y: number } | null = null;

    if (s.isWebcamMode) {
      const raw = s.screenGaze;
      const last = lastRawRef.current;
      if (!last || last.x !== raw.x || last.y !== raw.y) {
        lastRawRef.current = { x: raw.x, y: raw.y };
        newRaw = { x: raw.x, y: raw.y };      // chỉ gửi khi có mẫu webcam MỚI
      }
      const f = filteredRef.current ?? raw;    // ưu tiên gaze đã lọc từ backend
      rayNdc.set(f.x, f.y);
    }

    raycaster.setFromCamera(rayNdc, camera);
    const intersects = raycaster.intersectObjects(scene.children, true);
    const hit = intersects.find((i) => i.object.userData?.isTarget);

    let hoveredId: string | null = null;
    const targetVector = new THREE.Vector3();

    if (hit) {
      hoveredId = hit.object.name;
      targetVector.copy(hit.point);
    } else {
      raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), targetVector);
      // Hít nam châm: vật gần tia nhất trong SNAP_RADIUS
      let best = SNAP_RADIUS;
      for (const t of s.targets) {
        const p = new THREE.Vector3(...t.position).project(camera);
        if (p.z > 1) continue;
        const d = Math.hypot(p.x - rayNdc.x, p.y - rayNdc.y);
        if (d < best) { best = d; hoveredId = t.id; }
      }
    }

    // Gửi dữ liệu cho backend
    const normX = Math.max(0, Math.min(1, (targetVector.x + 5) / 10));
    const normY = Math.max(0, Math.min(1, (targetVector.z + 5) / 10));
    const now = performance.now();
    let velocity = 0;
    if (lastPosRef.current) {
      const dt = (now - lastPosRef.current.time) / 1000;
      if (dt > 0) velocity = Math.hypot(normX - lastPosRef.current.x, normY - lastPosRef.current.y) / dt;
    }
    lastPosRef.current = { x: normX, y: normY, time: now };

    if (socketRef.current?.connected) {
      socketRef.current.emit('gaze_data', {
        x: normX, y: normY, v: velocity, timestamp: now,
        nx: newRaw?.x, ny: newRaw?.y,
      });
    }

    if (hoveredId !== s.activeHoverTargetId) s.setHoverTarget(hoveredId);

    // Dwell có "thời gian ân hạn" thay vì reset ngay khi trượt 1 frame
    const d = dwellRef.current;
    const fixating = s.label === 0;
    const hoveredTarget = s.targets.find((t) => t.id === hoveredId);

    if (hoveredTarget && fixating && !hoveredTarget.isGrasped) {
      if (d.id !== hoveredId) { d.id = hoveredId; d.ms = 0; }
      d.ms += delta * 1000;
      d.lastSeen = now;
    } else if (d.id && now - d.lastSeen > GRACE_MS) {
      d.ms = Math.max(0, d.ms - delta * 1000 * 2);   // hết ân hạn: giảm dần, không reset cứng
      if (d.ms === 0) d.id = null;
    }

    const progress = Math.min(100, (d.ms / DWELL_MS) * 100);
    for (const t of s.targets) {
      if (t.isGrasped) continue;
      if (t.id === d.id) {
        if (progress >= 100) { s.updateTargetGraspProgress(t.id, 100, true); d.id = null; d.ms = 0; }
        else if (Math.abs(t.graspProgress - progress) > 3) s.updateTargetGraspProgress(t.id, progress, false);
      } else if (t.graspProgress !== 0) {
        s.updateTargetGraspProgress(t.id, 0, false);
      }
    }
  });

  return null;
};
```

---

## 3. (Tuỳ chọn) Hiệu chỉnh đa thức bậc 2 — công thức 2.1

GazeCloud đã tự calibrate, nhưng thường vẫn lệch có hệ thống ở mép màn hình. Sau khi `OnCalibrationComplete`, hiện 9 chấm (lưới 3×3 tại NDC ±0.8 và 0), mỗi chấm thu trung bình ~1 giây gaze thô rồi gửi:

```ts
socket.emit('calib_add', { raw: [avgRawX, avgRawY], target: [dotNdcX, dotNdcY] });
// ... sau chấm cuối:
socket.emit('calib_fit');
```

Từ đó mọi mẫu mới đi qua `W` trước One Euro. Nếu kết quả tệ hơn, gọi `calib.reset()` để về identity.

---

## Tinh chỉnh

| Triệu chứng | Chỉnh |
|---|---|
| Con trỏ vẫn rung khi nhìn yên | giảm `OneEuro.min_cutoff` (0.4 → 0.2), tăng `GazeStabilizer.radius` |
| Con trỏ bị trễ khi lia mắt | tăng `beta` (3 → 6) |
| Khó "gắp" trúng vật nhỏ | tăng `SNAP_RADIUS` (0.09 → 0.14) |
| Gắp nhầm vật bên cạnh | giảm `SNAP_RADIUS` hoặc tăng `DWELL_MS` |
| Hay bị mất tiến độ khi chớp mắt | tăng `GRACE_MS` |
