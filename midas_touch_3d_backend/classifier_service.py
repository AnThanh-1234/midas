import sys
import os
import numpy as np
import pickle

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

    def save_participant_model(self, sid: str, filepath: str = "saved_eye_model.pkl"):
        """Lưu mô hình của participant ra file."""
        model = self.participant_models.get(sid)
        if model is not None:
            try:
                with open(filepath, 'wb') as f:
                    pickle.dump(model, f)
                return True
            except Exception as e:
                print(f"[Save Model Error]: {e}")
        return False

    def load_participant_model(self, sid: str, filepath: str = "saved_eye_model.pkl"):
        """Tải mô hình của participant từ file."""
        if os.path.exists(filepath):
            try:
                with open(filepath, 'rb') as f:
                    model = pickle.load(f)
                self.participant_models[sid] = model
                return True
            except Exception as e:
                print(f"[Load Model Error]: {e}")
        return False

    def cleanup_participant(self, sid: str):
        """Giải phóng mô hình khi client ngắt kết nối."""
        if sid in self.participant_models:
            del self.participant_models[sid]

    def _threshold_label(self, velocity: float) -> int:
        """Fallback rõ ràng, nhẹ dựa trên ngưỡng vận tốc khi chưa có trained base model."""
        if velocity > 0.05:
            return 2  # Saccade
        elif velocity > 0.01:
            return 1  # Smooth Pursuit
        return 0  # Fixation

    def predict(self, buffer_data, sid: str = None):
        """
        buffer_data: list of dicts [{'x': float, 'y': float, 'v': float}, ...]
        sid: participant ID / socket ID để dùng đúng participant-base model
        Returns: integer label (0: Fixation, 1: Smooth Pursuit, 2: Saccade)
        """
        if not buffer_data:
            return 0

        last_v = buffer_data[-1].get('v', 0.0)

        # Nếu chưa đủ data hoặc chưa có base model đã huấn luyện, dùng fallback ngưỡng vận tốc nhẹ
        base_model = self.participant_models.get(sid) if sid else None
        if base_model is None:
            return self._threshold_label(last_v)

        try:
            x_arr = np.array([pt['x'] for pt in buffer_data])
            y_arr = np.array([pt['y'] for pt in buffer_data])
            v_arr = np.array([pt['v'] for pt in buffer_data])

            labels = self.classifier.fit_predict(x_arr, y_arr, v_arr, base_model=base_model)
            if len(labels) > 0:
                return int(labels[-1])
            return self._threshold_label(last_v)
        except Exception as e:
            print(f"[GMM-HMM Predict Exception ({sid})]: {e}")
            return self._threshold_label(last_v)
