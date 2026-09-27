# =====================================================================
# SUA LOI HIERARCHICAL GMM-HMM: 4 THAY DOI CHINH
#   (a) Chuan hoa (x, y, log_v) truoc khi fit tang 1 -> velocity khong bi
#       "nuot" boi x,y do lech scale (x,y ~0-1, velocity ~0.0001-0.02).
#   (b) KMeans-init cho tang 2 (thay vi de GMMHMM random init) -> EM co
#       diem xuat phat hop ly, giam nguy co "Degenerate mixture covariance".
#   (c) n_mix thich ung theo kich thuoc cum: cum qua nho -> n_mix=1
#       (tuong duong 1 Gaussian/state, giam tham so can hoc).
#   (d) Layer 2 duoc fit MOT LAN tren toan bo velocity CUA CHINH participant
#       do (KHONG pool cheo qua nguoi khac), roi CHI refit nhe (it iteration,
#       xuat phat tu tham so nay) cho cum nao du lon; cum qua nho thi dung
#       thang participant-base model de decode, KHONG refit rieng.
# =====================================================================
import warnings
import numpy as np
from hmmlearn.hmm import GMMHMM
from sklearn.cluster import KMeans as _KMeans

LOG_EPS4 = 1e-7
RANDOM_STATE = 42
MIN_SEG_LEN = 15

# ---- Cau hinh ----
LAYER1_COV_TYPE    = 'diag'   # 'full' de dung nhu main.py goc nhung de an
                               # toan (it du lieu/participant) nen dung diag

N_MIX_LAYER2_FULL  = 1        # TAM THOI GIAM VE 1 (giong GaussianHMM cell 10 cu)
                               # de kiem tra xem mixture co phai nguyen nhan
N_MIX_LAYER2_SMALL = 1
MIN_REFIT_SAMPLES  = 150      # nguong so mau de refit rieng cho sub-path
MIN_MIX_SAMPLES    = 300

# --- Cac ham tien ich phan doan ---
def compute_sse_curve(features, k_min=2, k_max=10):
    pts = features[:, :2]
    ks, vals = [], []
    for k in range(k_min, k_max + 1):
        m = _KMeans(n_clusters=k, init="k-means++", n_init=10, max_iter=300, random_state=RANDOM_STATE)
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
    if n == 0:
        return runs
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

def compute_velocity_thresholds(v):
    if len(v) == 0:
        return 0.01, 0.05
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

# --- 4 CAY CHOT CAI TIEN CUA HIERARCHICAL GMM-HMM ---

def zscore_xyv(features):
    """Chuan hoa (x, y, log_v) ve cung thang do truoc khi dua vao layer 1."""
    x, y, v = features[:, 0], features[:, 1], features[:, 2]
    log_v = np.log(v + LOG_EPS4)
    stacked = np.column_stack([x, y, log_v])
    mu  = stacked.mean(axis=0)
    std = stacked.std(axis=0)
    std[std < 1e-8] = 1.0
    return (stacked - mu) / std

def make_2d_features(velocity):
    """[log_velocity, log_acceleration] - 2D feature da chung minh tach
    Fixation/Smooth Pursuit tot hon 1D log_v rat nhieu (48.77% -> 83.92%
    o thi nghiem truoc). Ap dung lai cho tang 2 cua hierarchical model."""
    accel = np.abs(np.concatenate([[0], np.diff(velocity)]))
    log_v = np.log(velocity + LOG_EPS4)
    log_a = np.log(accel + LOG_EPS4)
    return np.column_stack([log_v, log_a])

def kmeans_init_means_layer2(feats2d_pool, n_mix):
    """KMeans tren 2D feature [log_v, log_accel] de lay diem khoi tao on
    dinh cho 3 state x n_mix component, thay vi random init."""
    n_clusters = 3 * n_mix
    if len(feats2d_pool) < n_clusters:
        repeat_factor = int(np.ceil(n_clusters / max(1, len(feats2d_pool))))
        feats2d_pool = np.tile(feats2d_pool, (repeat_factor, 1))[:n_clusters]
    km = _KMeans(n_clusters=n_clusters, n_init=20, random_state=RANDOM_STATE)
    km.fit(feats2d_pool)
    order = np.argsort(km.cluster_centers_[:, 0])   # sap theo log_v (cot 0)
    centers = km.cluster_centers_[order]
    return centers.reshape(3, n_mix, 2)             # (n_components, n_mix, 2)

def fit_layer1_gmmhmm(features, k, n_iter=200, random_state=RANDOM_STATE):
    """Layer 1: GMM-HMM tren (x, y, log_v) DA CHUAN HOA, n_components=k.
    n_mix=1 de giam tham so, covariance diag de giam nguy co suy bien."""
    feats_norm = zscore_xyv(features)
    model = GMMHMM(
        n_components=k, n_mix=1, covariance_type=LAYER1_COV_TYPE,
        n_iter=n_iter, tol=1e-4, random_state=random_state,
        min_covar=1e-3,
    )
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        model.fit(feats_norm)
        _, states = model.decode(feats_norm, algorithm='viterbi')
    return model, states

def build_participant_layer2_model(participant_velocities, n_mix=N_MIX_LAYER2_FULL,
                                    n_iter=300, random_state=RANDOM_STATE):
    """Fit MOT LAN tren TOAN BO velocity CUA CHINH 1 PARTICIPANT (KHONG pool
    cheo qua nguoi khac), dung feature 2D [log_v, log_accel] (khong phai
    1D log_v nua - day la nguyen nhan chinh gay tran ~55-60% o ban truoc,
    vi 1D khong tach duoc Fixation/Smooth Pursuit)."""
    feats2d = make_2d_features(participant_velocities)
    init_means = kmeans_init_means_layer2(feats2d, n_mix)
    model = GMMHMM(
        n_components=3, n_mix=n_mix, covariance_type='diag',
        n_iter=n_iter, tol=1e-4, random_state=random_state,
        min_covar=1e-4,
        init_params='stwc',   # KHONG init 'm' (means) vi minh tu dat ben duoi
    )
    model.means_ = init_means
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        model.fit(feats2d)
    return model

def refit_layer2_local(v_cluster, base_model, n_mix, n_iter=50, random_state=RANDOM_STATE):
    """Refit NHE (it iteration) rieng cho 1 sub-path, xuat phat tu tham so
    cua base_model (participant-base) thay vi random -> tranh suy bien khi
    mau khong qua nho nhung cung khong du lon de tu hoc tu dau. Dung 2D
    feature [log_v, log_accel] giong base_model."""
    feats2d = make_2d_features(v_cluster)
    model = GMMHMM(
        n_components=3, n_mix=n_mix, covariance_type='diag',
        n_iter=n_iter, tol=1e-3, random_state=random_state,
        min_covar=1e-4, init_params='',   # KHONG random init gi ca
    )
    # Copy tham so tu base_model lam diem xuat phat.
    if base_model.n_mix == n_mix:
        model.startprob_ = base_model.startprob_.copy()
        model.transmat_  = base_model.transmat_.copy()
        model.means_     = base_model.means_.copy()
        model.covars_    = base_model.covars_.copy()
        model.weights_   = base_model.weights_.copy()
    else:
        model.startprob_ = base_model.startprob_.copy()
        model.transmat_  = base_model.transmat_.copy()
        model.means_     = base_model.means_[:, :n_mix, :].copy()
        model.covars_    = base_model.covars_[:, :n_mix, ...].copy()
        w = base_model.weights_[:, :n_mix].copy()
        model.weights_   = w / w.sum(axis=1, keepdims=True)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            model.fit(feats2d)
        return model
    except Exception:
        return base_model   # refit loi -> dung tam base_model (khong refit)

def decode_layer2(model, v_cluster):
    feats2d = make_2d_features(v_cluster)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        _, states = model.decode(feats2d, algorithm='viterbi')
    # sap xep nhan theo trung binh log-velocity (cot 0) cua tung state,
    # KHONG lay trung binh ca 2 cot vi log_accel co the lam sai thu tu
    comp_means_v = np.array([model.means_[s][:, 0].mean() for s in range(3)])
    order  = np.argsort(comp_means_v)
    remap  = {old: new for new, old in enumerate(order)}
    return np.array([remap[s] for s in states])

def classify_sequence_hierarchical_v2(features, participant_layer2_model=None,
                                       k_min=2, k_max=10, min_seg_len=MIN_SEG_LEN):
    n = len(features)
    if n == 0:
        return np.array([], dtype=int), {'k': 0, 'n_segments': 0}

    velocities = features[:, 2]
    thr_lo, thr_hi = compute_velocity_thresholds(velocities)

    # Neu chua co participant_layer2_model, fit base model tren sequence hien tai
    if participant_layer2_model is None:
        if n >= 3:
            try:
                participant_layer2_model = build_participant_layer2_model(velocities, n_mix=N_MIX_LAYER2_FULL)
            except Exception:
                participant_layer2_model = None

    if participant_layer2_model is None or n < min_seg_len:
        return velocity_threshold_fallback(velocities, thr_lo, thr_hi), {'k': 1, 'n_segments': 1}

    actual_k_max = min(k_max, max(2, n // 2))
    actual_k_min = min(k_min, actual_k_max)

    # Step 0: SSE va Elbow K
    if actual_k_max > actual_k_min:
        try:
            kv, sv = compute_sse_curve(features, actual_k_min, actual_k_max)
            k = choose_elbow_k(kv, sv)
        except Exception:
            k = 2
    else:
        k = actual_k_min

    # Step 1: Coarse Segmentation - Fit Layer 1 GMM-HMM tren Z-Score (x, y, log_v)
    try:
        _, cluster_states = fit_layer1_gmmhmm(features, k)
    except Exception:
        cluster_states = np.zeros(n, dtype=int)
        k = 1

    # QUAN TRONG: chuyen nhan-theo-tung-diem (cluster_states) thanh cac
    # SUB-PATH LIEN TUC theo thoi gian (runs_from_states + merge_short_runs).
    # KHONG duoc dung np.where(cluster_states==c) roi gop tat ca cac diem cung nhan
    runs = runs_from_states(cluster_states)
    sub_path_ranges = merge_short_runs(runs, min_seg_len)
    sub_path_ranges = [(s, e) for s, e, _ in sub_path_ranges]

    # Step 2 - moi SUB-PATH LIEN TUC: qua nho -> dung thang participant-base model;
    # du lon -> refit nhe xuat phat tu chinh participant-base model do.
    pred = np.zeros(n, dtype=int)
    for start, end in sub_path_ranges:
        v_c = velocities[start:end]
        if len(v_c) == 0:
            continue
        if len(v_c) < MIN_REFIT_SAMPLES:
            model_c = participant_layer2_model
        else:
            n_mix_c = (N_MIX_LAYER2_FULL if len(v_c) >= MIN_MIX_SAMPLES
                       else N_MIX_LAYER2_SMALL)
            model_c = refit_layer2_local(v_c, participant_layer2_model, n_mix_c)
        try:
            pred[start:end] = decode_layer2(model_c, v_c)
        except Exception:
            v_thr_lo, v_thr_hi = compute_velocity_thresholds(v_c)
            pred[start:end] = velocity_threshold_fallback(v_c, v_thr_lo, v_thr_hi)

    # Step 3: Lam muot nhan
    pred = smooth_labels(pred, window=3)
    return pred, {'k': k, 'n_segments': len(sub_path_ranges)}

# Compatibility alias
classify_sequence = classify_sequence_hierarchical_v2

class NotebookClassifier:
    def __init__(self, k_max=10, min_seg_len=15, n_mix=N_MIX_LAYER2_FULL):
        self.k_max = k_max
        self.min_seg_len = min_seg_len
        self.n_mix = n_mix
        self.base_model = None

    def fit_base_model(self, velocities):
        """Fit participant-base model tren toan bo chuoi van toc."""
        if len(velocities) >= 3:
            self.base_model = build_participant_layer2_model(velocities, n_mix=self.n_mix)
        return self.base_model

    def fit_predict(self, x_arr, y_arr, v_arr, base_model=None):
        features = np.column_stack((x_arr, y_arr, v_arr))
        model_to_use = base_model if base_model is not None else self.base_model
        pred, _ = classify_sequence_hierarchical_v2(
            features,
            participant_layer2_model=model_to_use,
            k_min=2,
            k_max=self.k_max,
            min_seg_len=self.min_seg_len
        )
        return pred
