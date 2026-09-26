import sys
import os
import numpy as np

ALGORITHM_DIR = r"D:\cac_mon_hoc\HTTM\eyemovement_update_v1"
if ALGORITHM_DIR not in sys.path:
    sys.path.insert(0, ALGORITHM_DIR)

from hierarchical_gmm_hmm import HierarchicalGMMHMMClassifier

class EyeMovementClassifierService:
    def __init__(self, window_size: int = 30):
        self.window_size = window_size
        self.classifier = HierarchicalGMMHMMClassifier(k_max=6, max_iter=200)

    def predict(self, buffer_data):
        """
        buffer_data: list of dicts [{'x': float, 'y': float, 'v': float}, ...]
        Returns: integer label (0: Fixation, 1: Smooth Pursuit, 2: Saccade)
        """
        # Nếu chưa đủ data (tùy ý định nghĩa ngưỡng tối thiểu), trả về kết quả dựa theo vận tốc.
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

            labels = self.classifier.fit_predict(x_arr, y_arr, v_arr)
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
