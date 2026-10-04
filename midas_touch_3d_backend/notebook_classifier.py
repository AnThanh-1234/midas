# =====================================================================
# PIPELINE GMM-HMM HAI TẦNG (GMM_HMM_full_layer.py)
#   - Layer 1: GMM-HMM phân đoạn chuỗi điểm nhìn trên (x, y) với K chọn bằng Elbow K-Means.
#   - Layer 2: GMM-HMM 3 trạng thái phân loại vận tốc (v) cho từng phân đoạn đủ dài.
#   - Velocity mapping: K-Means 3 cụm gom mean velocity gán nhãn Fixation / Smooth Pursuit / Saccade.
#   - Tham số: N_MIX = 1, covariance_type = 'spherical', MIN_SEG_LEN = 10, standardize = False.
# =====================================================================
import warnings
import numpy as np
import pandas as pd
from hmmlearn.hmm import GMMHMM
from sklearn.cluster import KMeans

warnings.filterwarnings("ignore")

RANDOM_STATE = 42
MIN_SEG_LEN = 10
N_MIX_LAYER2_FULL = 1
N_MIX = 1
COVARIANCE_TYPE = 'spherical'
STANDARDIZE = False

CFG = {
    "seed": RANDOM_STATE,
    "k_max": 9,
    "kmeans_max_iter": 100,
    "kmeans_restarts": 10,
    "l1_features": ("x", "y"),
    "l2_features": ("v",),
    "n_mix": N_MIX,
    "covariance_type": COVARIANCE_TYPE,
    "n_iter": 50,
    "tol": 1e-5,
    "n_restarts": 5,
    "min_seg_len": MIN_SEG_LEN,
    "standardize": STANDARDIZE,
}


def scale(data, enabled):
    if enabled:
        from sklearn.preprocessing import StandardScaler
        return StandardScaler().fit_transform(data)
    return data


def kmeans_sse(data, n_clusters, max_iter, restarts, rng):
    """Tính SSE bằng K-Means tự cài đặt, không dùng sklearn KMeans."""
    best_sse = np.inf
    for _ in range(restarts):
        centers = data[rng.choice(len(data), n_clusters, replace=False)].copy()
        for _ in range(max_iter):
            distances = ((data[:, None, :] - centers[None, :, :]) ** 2).sum(2)
            labels = distances.argmin(1)
            new_centers = np.array([
                data[labels == cluster].mean(0)
                if np.any(labels == cluster) else centers[cluster]
                for cluster in range(n_clusters)
            ])
            if np.allclose(new_centers, centers):
                break
            centers = new_centers
        sse = float(((data - centers[labels]) ** 2).sum())
        best_sse = min(best_sse, sse)
    return best_sse


def choose_k(data, cfg, requested_k=None):
    if requested_k is not None:
        if requested_k < 1 or requested_k > len(data):
            return min(max(1, requested_k), len(data))
        return requested_k

    max_k = min(cfg["k_max"], len(data))
    ks = np.arange(1, max_k + 1)
    if len(ks) < 3:
        return int(ks[-1])

    rng = np.random.default_rng(cfg["seed"])
    sse = np.array([
        kmeans_sse(
            data,
            int(k),
            cfg["kmeans_max_iter"],
            cfg["kmeans_restarts"],
            rng,
        )
        for k in ks
    ])
    x = (ks - ks.min()) / (ks.max() - ks.min() + 1e-12)
    y = (sse - sse.min()) / (sse.max() - sse.min() + 1e-12)
    distance = np.abs((y[-1] - y[0]) * x - (x[-1] - x[0]) * y
                      + x[-1] * y[0] - y[-1] * x[0])
    return int(ks[int(distance.argmax())])


def fit_gmmhmm(data, n_states, cfg, seed):
    """Thử nhiều restart để fit GMMHMM."""
    mix_values = list(dict.fromkeys((cfg["n_mix"], 1)))
    for n_mix in mix_values:
        best_model = None
        best_score = -np.inf
        for restart in range(cfg["n_restarts"]):
            try:
                model = GMMHMM(
                    n_components=n_states,
                    n_mix=n_mix,
                    covariance_type=cfg["covariance_type"],
                    n_iter=cfg["n_iter"],
                    tol=cfg["tol"],
                    min_covar=1e-3,
                    random_state=seed + restart,
                    verbose=False,
                )
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    model.fit(data)
                    score = float(model.score(data))
                if np.isfinite(score) and score > best_score:
                    best_model, best_score = model, score
            except (ValueError, np.linalg.LinAlgError, FloatingPointError):
                continue
        if best_model is not None:
            return best_model
    return None


def velocity_mapping(stats, cfg):
    """Tạo mapping state cục bộ -> lớp vận tốc từ toàn bộ section."""
    velocities = np.log10(np.maximum(np.asarray(stats)[:, 2], 0) + 1e-6)
    if len(velocities) >= 3:
        model = KMeans(
            n_clusters=3,
            n_init=10,
            random_state=cfg["seed"],
        ).fit(velocities.reshape(-1, 1))
        order = np.argsort(model.cluster_centers_.ravel())
        cluster_to_class = {
            int(cluster): rank for rank, cluster in enumerate(order)
        }
        return {
            (int(section), int(state)): cluster_to_class[int(cluster)]
            for (section, state, _), cluster in zip(stats, model.labels_)
        }, model.cluster_centers_.ravel()[order]

    # Không đủ state để chạy K-Means 3 cụm: xếp trực tiếp theo vận tốc.
    order = np.argsort(velocities)
    return {
        (int(stats[index][0]), int(stats[index][1])): min(rank, 2)
        for rank, index in enumerate(order)
    }, velocities[order]


def velocity_threshold_fallback(velocities):
    if len(velocities) == 0:
        return np.array([], dtype=int)
    thr_lo = float(np.percentile(velocities, 50))
    thr_hi = float(np.percentile(velocities, 85))
    res = np.zeros(len(velocities), dtype=int)
    res[velocities > thr_hi] = 2
    res[(velocities > thr_lo) & (velocities <= thr_hi)] = 1
    return res


def classify_sequence_gmmhmm_full(features, cfg=None, requested_k=None):
    if cfg is None:
        cfg = CFG.copy()

    n = len(features)
    if n == 0:
        return np.array([], dtype=int), {'k': 0, 'n_segments': 0}

    if isinstance(features, pd.DataFrame):
        df = features[["x", "y", "v"]].copy()
    else:
        df = pd.DataFrame(features[:, :3], columns=["x", "y", "v"])

    velocity = df["v"].to_numpy()
    if n < 3:
        return velocity_threshold_fallback(velocity), {'k': 1, 'n_segments': 1}

    try:
        xy = df[["x", "y"]].to_numpy()
        k = choose_k(xy, cfg, requested_k)
        layer1_input = scale(df[["x", "y"]].to_numpy(), cfg["standardize"])
        layer1 = fit_gmmhmm(layer1_input, k, cfg, cfg["seed"])

        if layer1 is None:
            return velocity_threshold_fallback(velocity), {'k': 1, 'n_segments': 1}

        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            _, segment_states = layer1.decode(layer1_input, algorithm="viterbi")

        local_states = np.full(n, -1, dtype=int)
        stats = []
        tiny_sections = []

        for section in np.unique(segment_states):
            indices = np.flatnonzero(segment_states == section)
            if len(indices) < cfg["min_seg_len"]:
                tiny_sections.append(indices)
                continue

            layer2_input = scale(
                df.iloc[indices][["v"]].to_numpy(),
                cfg["standardize"],
            )
            layer2 = fit_gmmhmm(
                layer2_input,
                3,
                cfg,
                cfg["seed"] + 100 + int(section),
            )
            if layer2 is None:
                tiny_sections.append(indices)
                continue

            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                _, states = layer2.decode(layer2_input, algorithm="viterbi")

            local_states[indices] = states
            for state in np.unique(states):
                state_velocity = velocity[indices[states == state]]
                stats.append((section, state, float(state_velocity.mean())))

        if not stats:
            return velocity_threshold_fallback(velocity), {'k': k, 'n_segments': len(tiny_sections)}

        mapping, centers = velocity_mapping(stats, cfg)
        prediction = np.full(n, -1, dtype=int)

        for index in np.flatnonzero(local_states >= 0):
            key = (int(segment_states[index]), int(local_states[index]))
            if key in mapping:
                prediction[index] = mapping[key]
            else:
                prediction[index] = 0

        # Section ngắn/fail dùng tâm velocity global
        for indices in tiny_sections:
            if len(centers) > 0:
                distances = np.abs(
                    np.log10(np.maximum(velocity[indices], 0) + 1e-6)[:, None]
                    - centers[None, :]
                )
                prediction[indices] = distances.argmin(1).clip(max=2)
            else:
                prediction[indices] = velocity_threshold_fallback(velocity[indices])

        if np.any(prediction < 0):
            unassigned = np.flatnonzero(prediction < 0)
            prediction[unassigned] = velocity_threshold_fallback(velocity[unassigned])

        return prediction, {'k': k, 'n_segments': len(np.unique(segment_states))}
    except Exception:
        return velocity_threshold_fallback(velocity), {'k': 1, 'n_segments': 1}


# Compatibility aliases
classify_sequence = classify_sequence_gmmhmm_full
classify_sequence_hierarchical_v2 = classify_sequence_gmmhmm_full


def build_participant_layer2_model(participant_velocities, n_mix=N_MIX, n_iter=50, random_state=RANDOM_STATE):
    """Hàm tương thích hỗ trợ tạo/huấn luyện model cho participant."""
    v_input = scale(participant_velocities.reshape(-1, 1), STANDARDIZE)
    cfg = CFG.copy()
    cfg["n_mix"] = n_mix
    return fit_gmmhmm(v_input, 3, cfg, random_state)


class NotebookClassifier:
    def __init__(self, k_max=9, min_seg_len=MIN_SEG_LEN, n_mix=N_MIX, covariance_type=COVARIANCE_TYPE, standardize=STANDARDIZE):
        self.cfg = CFG.copy()
        self.cfg["k_max"] = k_max
        self.cfg["min_seg_len"] = min_seg_len
        self.cfg["n_mix"] = n_mix
        self.cfg["covariance_type"] = covariance_type
        self.cfg["standardize"] = standardize
        self.base_model = None

    def fit_base_model(self, velocities):
        if len(velocities) >= 3:
            self.base_model = build_participant_layer2_model(velocities, n_mix=self.cfg["n_mix"])
        return self.base_model

    def fit_predict(self, x_arr, y_arr, v_arr, base_model=None):
        features = np.column_stack((x_arr, y_arr, v_arr))
        pred, _ = classify_sequence_gmmhmm_full(features, cfg=self.cfg)
        return pred

