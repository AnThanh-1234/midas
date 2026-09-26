import numpy as np
import warnings
from hmmlearn.hmm import GaussianHMM
from sklearn.cluster import KMeans

RANDOM_STATE = 42
LOG_EPS = 1e-7
MIN_FIT_LEN = 30
MIN_SEG_LEN = 15

def compute_sse_curve(features, k_min=2, k_max=10):
    pts = features[:, :2]
    ks, vals = [], []
    for k in range(k_min, k_max + 1):
        m = KMeans(n_clusters=k, init="k-means++", n_init=10, max_iter=300, random_state=RANDOM_STATE)
        m.fit(pts)
        ks.append(k)
        vals.append(float(m.inertia_))
    return ks, vals

def choose_elbow_k(k_values, sse_values):
    if len(k_values) <= 2:
        return int(k_values[0])
    p1 = np.array([k_values[0],  sse_values[0]])
    p2 = np.array([k_values[-1], sse_values[-1]])
    line = p2 - p1
    line_len = np.linalg.norm(line)
    if line_len < 1e-12:
        return 3
    dists = []
    for k, s in zip(k_values, sse_values):
        vec = np.array([k, s]) - p1
        cross_2d = line[0] * vec[1] - line[1] * vec[0]
        dists.append(abs(cross_2d) / line_len)
    return int(np.clip(k_values[int(np.argmax(dists))], 2, 8))

def runs_from_states(states):
    n = len(states)
    runs, start = [], 0
    if n == 0: return runs
    for i in range(1, n):
        if states[i] != states[i - 1]:
            runs.append((start, i, int(states[start])))
            start = i
    runs.append((start, n, int(states[start])))
    return runs

def merge_short_runs(runs, min_len):
    if len(runs) <= 1:
        return runs
    merged = list(runs)
    changed = True
    while changed and len(merged) > 1:
        changed = False
        for i, (s, e, st) in enumerate(merged):
            if e - s < min_len:
                if i > 0:
                    ps, pe, pst = merged[i - 1]
                    merged[i - 1] = (ps, e, pst)
                    del merged[i]
                else:
                    ns, ne, nst = merged[i + 1]
                    merged[i] = (s, ne, nst)
                    del merged[i + 1]
                changed = True
                break
    return merged

def segment_sequence_round1(features, k, min_len=MIN_SEG_LEN):
    xy = features[:, :2]
    km = KMeans(n_clusters=k, init='k-means++', n_init=10, max_iter=300, random_state=RANDOM_STATE)
    cluster_ids = km.fit_predict(xy)
    runs = runs_from_states(cluster_ids)
    merged = merge_short_runs(runs, min_len)
    return [(s, e) for s, e, _ in merged]

def compute_velocity_thresholds(v):
    return float(np.percentile(v, 50)), float(np.percentile(v, 85))

def velocity_threshold_fallback(v_seg, thr_lo, thr_hi):
    res = np.zeros(len(v_seg), dtype=int)
    res[v_seg > thr_hi] = 2
    res[(v_seg > thr_lo) & (v_seg <= thr_hi)] = 1
    return res

def smooth_labels(labels, window=3):
    n = len(labels)
    if n < window:
        return labels
    smoothed = labels.copy()
    half = window // 2
    for i in range(half, n - half):
        w = labels[i - half:i + half + 1]
        vals, counts = np.unique(w, return_counts=True)
        smoothed[i] = vals[np.argmax(counts)]
    return smoothed

def fit_velocity_hmm(v_all):
    if len(v_all) < MIN_FIT_LEN:
        return None
    log_v = np.log(v_all + LOG_EPS).reshape(-1, 1)
    try:
        km_init = KMeans(n_clusters=3, n_init=20, random_state=RANDOM_STATE)
        km_init.fit(log_v)
        init_means = np.sort(km_init.cluster_centers_.flatten()).reshape(3, 1)
    except Exception:
        p = np.percentile(log_v, [20, 55, 90])
        init_means = p.reshape(3, 1)
    model = GaussianHMM(
        n_components=3, covariance_type='diag',
        n_iter=300, tol=1e-4, min_covar=1e-4,
        init_params='stc',
        random_state=RANDOM_STATE
    )
    model.means_ = init_means
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            model.fit(log_v)
        order = np.argsort(model.means_.flatten())
        covars_raw = model.covars_.copy()
        model.means_ = model.means_[order]
        model.covars_ = covars_raw[order].reshape(3, -1)
        model.startprob_ = model.startprob_[order]
        model.transmat_ = model.transmat_[order][:, order]
        return model
    except Exception:
        return None

def decode_subpath(model, v_sub, thr_lo, thr_hi):
    if model is None or len(v_sub) < 2:
        return velocity_threshold_fallback(v_sub, thr_lo, thr_hi)
    try:
        log_v_sub = np.log(v_sub + LOG_EPS).reshape(-1, 1)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            _, states = model.decode(log_v_sub, algorithm='viterbi')
        return states
    except Exception:
        return velocity_threshold_fallback(v_sub, thr_lo, thr_hi)

def classify_sequence(features, k_min=2, k_max=10, min_seg_len=MIN_SEG_LEN):
    n = len(features)
    if n < min_seg_len:
        velocities = features[:, 2]
        thr_lo, thr_hi = 0.01, 0.05
        if len(velocities) > 0:
            thr_lo, thr_hi = compute_velocity_thresholds(velocities)
        return velocity_threshold_fallback(velocities, thr_lo, thr_hi)

    velocities = features[:, 2]
    thr_lo, thr_hi = compute_velocity_thresholds(velocities)
    hmm_model = fit_velocity_hmm(velocities)
    
    actual_k_max = min(k_max, n // 2)
    actual_k_min = min(k_min, actual_k_max)
    
    if actual_k_min < 2:
        pred = decode_subpath(hmm_model, velocities, thr_lo, thr_hi)
        return smooth_labels(pred, window=3)

    kv, sv = compute_sse_curve(features, actual_k_min, actual_k_max)
    k = choose_elbow_k(kv, sv)
    sub_path_ranges = segment_sequence_round1(features, k, min_len=min_seg_len)
    pred = np.zeros(n, dtype=int)
    for start, end in sub_path_ranges:
        pred[start:end] = decode_subpath(hmm_model, velocities[start:end], thr_lo, thr_hi)
    pred = smooth_labels(pred, window=3)
    return pred

class NotebookClassifier:
    def __init__(self, k_max=10, min_seg_len=15):
        self.k_max = k_max
        self.min_seg_len = min_seg_len

    def fit_predict(self, x_arr, y_arr, v_arr):
        features = np.column_stack((x_arr, y_arr, v_arr))
        return classify_sequence(features, k_min=2, k_max=self.k_max, min_seg_len=self.min_seg_len)
