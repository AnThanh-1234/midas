import sys
import os
import numpy as np

from notebook_classifier import (
    NotebookClassifier,
    build_participant_layer2_model,
    N_MIX_LAYER2_FULL
)

class EyeMovementClassifierService:
    def __init__(self, window_size: int = 30):
        self.window_size = window_size
        self.classifier = NotebookClassifier(k_max=10, min_seg_len=15)
        # Quản lý participant-base model riêng cho từng participant/session (tránh pool chéo)
        self.participant_models = {}

    def init_participant_model(self, sid: str, velocities: np.ndarray):
        """Fit participant-base model 1 lần trên toàn bộ vận tốc của chính participant."""
        try:
            if len(velocities) >= 3:
                model = build_participant_layer2_model(velocities, n_mix=N_MIX_LAYER2_FULL)
                self.participant_models[sid] = model
                return model
        except Exception as e:
            print(f"[Init Participant Base Model Error ({sid})]: {e}")
        return None

    def cleanup_participant(self, sid: str):
        """Giải phóng mô hình khi client ngắt kết nối."""
        if sid in self.participant_models:
            del self.participant_models[sid]

    def predict(self, buffer_data, sid: str = None):
        """
        buffer_data: list of dicts [{'x': float, 'y': float, 'v': float}, ...]
        sid: participant ID / socket ID để dùng đúng participant-base model
        Returns: integer label (0: Fixation, 1: Smooth Pursuit, 2: Saccade)
        """
        # Nếu chưa đủ data (ngưỡng tối thiểu), trả về kết quả fallback an toàn dựa theo ngưỡng vận tốc
        if not buffer_data or len(buffer_data) < 5:
            last_v = buffer_data[-1]['v'] if buffer_data else 0.0
            if last_v > 0.05:
                return 2  # Saccade
            elif last_v > 0.01:
                return 1  # Smooth Pursuit
            return 0  # Fixation

        try:
            x_arr = np.array([pt['x'] for pt in buffer_data])
            y_arr = np.array([pt['y'] for pt in buffer_data])
            v_arr = np.array([pt['v'] for pt in buffer_data])

            base_model = self.participant_models.get(sid) if sid else None
            labels = self.classifier.fit_predict(x_arr, y_arr, v_arr, base_model=base_model)
            if len(labels) > 0:
                return int(labels[-1])
            return 0
        except Exception as e:
            print(f"[Classifier Error]: {e}")
            # Fallback an toàn khi lỗi
            last_v = buffer_data[-1]['v']
            if last_v > 0.05:
                return 2
            elif last_v > 0.01:
                return 1
            return 0
