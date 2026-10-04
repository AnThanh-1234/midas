"""
gaze_filter.py - Làm mượt ánh nhìn trong không gian màn hình (NDC [-1, 1]).

Pipeline cho mỗi mẫu gaze thô (nx, ny):
    PolyCalibrator (tuỳ chọn, công thức 2.1 trong file md)
        -> One Euro filter (khử nhiễu thích ứng theo tốc độ)
        -> GazeStabilizer (khoá tâm khi Fixation, có hysteresis)
"""
import math
import numpy as np


# ---------------------------------------------------------------------
# 1. ONE EURO FILTER
#    Đứng yên  -> cutoff thấp -> rất mượt, hết rung
#    Quét nhanh -> cutoff tăng -> gần như không bị trễ
# ---------------------------------------------------------------------
def _alpha(dt: float, cutoff: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class _LowPass:
    def __init__(self):
        self.s = None

    def __call__(self, x: float, a: float) -> float:
        self.s = x if self.s is None else a * x + (1.0 - a) * self.s
        return self.s


class OneEuro:
    def __init__(self, min_cutoff=0.4, beta=3.0, d_cutoff=1.0):
        # Đơn vị: x tính bằng NDC, t tính bằng giây.
        # min_cutoff ↓  => mượt hơn khi đứng yên (nhưng trễ hơn)
        # beta       ↑  => bớt trễ khi chuyển động nhanh
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.t_prev = None
        self.lp_x = _LowPass()
        self.lp_dx = _LowPass()

    def __call__(self, x: float, t: float) -> float:
        if self.t_prev is None:
            self.t_prev = t
            self.lp_x(x, 1.0)
            self.lp_dx(0.0, 1.0)
            return x
        dt = max(t - self.t_prev, 1e-3)
        dx = (x - self.lp_x.s) / dt
        dx_hat = self.lp_dx(dx, _alpha(dt, self.d_cutoff))
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        x_hat = self.lp_x(x, _alpha(dt, cutoff))
        self.t_prev = t
        return x_hat


# ---------------------------------------------------------------------
# 2. GAZE STABILIZER (vùng chết + hysteresis)
#    Khi đang Fixation: giữ "điểm neo", bỏ qua dao động nhỏ.
#    Chỉ nhả neo khi gaze ra ngoài bán kính trong N mẫu liên tiếp.
# ---------------------------------------------------------------------
class GazeStabilizer:
    def __init__(self, radius=0.12, exit_frames=3, drift=0.05):
        self.radius = radius          # NDC; 0.12 ~ 6% chiều rộng màn hình
        self.exit_frames = exit_frames
        self.drift = drift            # neo trôi nhẹ theo gaze để theo kịp chuyển động chậm
        self.anchor = None
        self.out_count = 0

    def reset(self, x=None, y=None):
        self.anchor = None if x is None else np.array([x, y], dtype=float)
        self.out_count = 0

    def update(self, x: float, y: float):
        p = np.array([x, y], dtype=float)
        if self.anchor is None:
            self.anchor = p
            return x, y
        if np.linalg.norm(p - self.anchor) <= self.radius:
            self.out_count = 0
            self.anchor = self.anchor + self.drift * (p - self.anchor)
        else:
            self.out_count += 1
            if self.out_count >= self.exit_frames:
                self.anchor = p
                self.out_count = 0
        return float(self.anchor[0]), float(self.anchor[1])


# ---------------------------------------------------------------------
# 3. POLY CALIBRATOR - công thức 2.1 (đa thức bậc 2) dùng làm bước HIỆU CHỈNH PHẦN DƯ
#    out = raw + [1, x, y, x², y², xy] @ W
#    Ridge: không phạt hệ số hằng, phạt nhẹ phần còn lại để không overfit
#    khi có ít điểm. Chưa fit -> trả nguyên giá trị (identity).
# ---------------------------------------------------------------------
class PolyCalibrator:
    def __init__(self, lam=0.05, min_samples=6):
        self.lam = lam
        self.min_samples = min_samples
        self.raw = []
        self.target = []
        self.W = None

    @staticmethod
    def _phi(x, y):
        return np.array([1.0, x, y, x * x, y * y, x * y])

    def add_sample(self, raw_xy, target_xy):
        self.raw.append(list(raw_xy))
        self.target.append(list(target_xy))

    def fit(self) -> bool:
        if len(self.raw) < self.min_samples:
            return False
        X = np.array(self.raw, dtype=float)
        T = np.array(self.target, dtype=float)
        Phi = np.stack([self._phi(x, y) for x, y in X])
        penalty = self.lam * np.diag([0, 1, 1, 1, 1, 1])
        self.W = np.linalg.solve(Phi.T @ Phi + penalty, Phi.T @ (T - X))  # (6, 2)
        return True

    def apply(self, x, y):
        if self.W is None:
            return x, y
        dx, dy = self._phi(x, y) @ self.W
        return (float(np.clip(x + dx, -1.2, 1.2)), float(np.clip(y + dy, -1.2, 1.2)))

    def reset(self):
        self.raw, self.target, self.W = [], [], None


# ---------------------------------------------------------------------
# 4. GAZE SMOOTHER - ghép tất cả, 1 instance / client
# ---------------------------------------------------------------------
class GazeSmoother:
    def __init__(self):
        self.calib = PolyCalibrator()
        self.fx = OneEuro()
        self.fy = OneEuro()
        self.stab = GazeStabilizer()
        self.last = (None, None)

    def process(self, nx, ny, t, stable_label):
        """
        nx, ny: gaze thô dạng NDC (None nếu frame này không có mẫu mới)
        t: timestamp giây
        stable_label: 0 Fixation / 1 Smooth Pursuit / 2 Saccade (đã debounce)
        """
        if nx is None or ny is None:
            return self.last
        x, y = self.calib.apply(nx, ny)
        x, y = self.fx(x, t), self.fy(y, t)
        if stable_label == 0:
            x, y = self.stab.update(x, y)
        else:
            self.stab.reset(x, y)   # Pursuit/Saccade: nhả neo, bám theo ngay
        self.last = (x, y)
        return self.last
