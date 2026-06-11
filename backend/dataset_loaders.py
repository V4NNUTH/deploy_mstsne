"""
Dataset loaders for ms-tsne-explorer backend.
Maps dataset_id → loader function that returns (X_hd, labels, meta)
All paths relative to /app/dataset/ inside Docker container.
"""
import os
import numpy as np
import pandas as pd
import subprocess
import shutil

DATASET_BASE = "/app/dataset"
#DATASET_BASE = "/home/ams-lab/Desktop/vannuth/UNamur/ms-tsne-explorer/dataset"


def load_anuran_calls():
    path = os.path.join(DATASET_BASE, "1_Anuran_Calls/anuran+calls+mfccs/Frogs_MFCCs.csv")
    df = pd.read_csv(path)
    mfcc_cols = [c for c in df.columns if 'MFCC' in c.upper()]
    X_hd = df[mfcc_cols].values.astype(np.float64)
    label_col = 'Species' if 'Species' in df.columns else df.columns[-1]
    labels_raw = df[label_col].values
    unique_labels = np.unique(labels_raw)
    label_to_idx = {l: i for i, l in enumerate(unique_labels)}
    clusters = np.array([label_to_idx[l] for l in labels_raw])
    return X_hd, clusters, {
        "name": "Anuran Calls (MFCCs)",
        "N": len(X_hd), "features": X_hd.shape[1],
        "n_classes": len(unique_labels),
        "class_names": list(unique_labels),
        "label_col": label_col,
    }


def load_ccpp():
    path = os.path.join(DATASET_BASE,
        "2_Combined_cycle_power_plant/combined+cycle+power+plant/CCPP/Folds5x2_pp.xlsx")
    df = pd.read_excel(path)
    feature_cols = ['AT', 'V', 'AP', 'RH']
    X_hd = df[feature_cols].values.astype(np.float64)
    PE = df['PE'].values
    N_BINS = 5
    pe_bins = pd.qcut(PE, q=N_BINS, labels=[f'Q{i+1}' for i in range(N_BINS)])
    labels_raw = pe_bins.astype(str).to_numpy()
    unique_labels = np.unique(labels_raw)
    label_to_idx = {l: i for i, l in enumerate(unique_labels)}
    clusters = np.array([label_to_idx[l] for l in labels_raw])
    return X_hd, clusters, {
        "name": "Combined Cycle Power Plant",
        "N": len(X_hd), "features": X_hd.shape[1],
        "n_classes": len(unique_labels),
        "class_names": list(unique_labels),
        "label_col": "PE (binned)",
    }


def load_musk_v2():
    csv_path = os.path.join(DATASET_BASE,
        "3_Musk_Version_2/musk+version+2/clean2.data")
    z_path = csv_path + ".Z"
    if not os.path.exists(csv_path) and os.path.exists(z_path):
        shutil.copy(z_path, csv_path + ".Z")
        subprocess.run(['uncompress', csv_path + ".Z"], capture_output=True)
    rows = []
    with open(csv_path, 'r') as f:
        for line in f:
            line = line.strip().rstrip('.')
            if line:
                rows.append(line.split(','))
    col_names = (['molecule_name', 'conformation_name'] +
                 [f'f{i}' for i in range(1, 167)] + ['class'])
    df = pd.DataFrame(rows, columns=col_names)
    feature_cols = [f'f{i}' for i in range(1, 167)]
    df[feature_cols] = df[feature_cols].apply(pd.to_numeric)
    df['class'] = pd.to_numeric(df['class'])
    X_hd = df[feature_cols].values.astype(np.float64)
    y = df['class'].values.astype(int)
    clusters = y.copy()
    return X_hd, clusters, {
        "name": "Musk Version 2",
        "N": len(X_hd), "features": X_hd.shape[1],
        "n_classes": 2,
        "class_names": ["Non-Musk", "Musk"],
        "label_col": "class",
    }


def load_spambase():
    path = os.path.join(DATASET_BASE, "4_Spambase/spambase/spambase.data")
    df = pd.read_csv(path, header=None)
    X_hd = df.iloc[:, :-1].values.astype(np.float64)
    y = df.iloc[:, -1].values.astype(int)
    clusters = y.copy()
    return X_hd, clusters, {
        "name": "Spambase",
        "N": len(X_hd), "features": X_hd.shape[1],
        "n_classes": 2,
        "class_names": ["Not Spam", "Spam"],
        "label_col": "class",
    }


def load_gesture():
    data_dir = os.path.join(DATASET_BASE,
        "5_Gesture_phase_segmentation/gesture+phase+segmentation")
    va3_files = ['a1_va3.csv','a2_va3.csv','a3_va3.csv',
                 'b1_va3.csv','b3_va3.csv','c1_va3.csv','c3_va3.csv']
    dfs = []
    for fname in va3_files:
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            df_i = pd.read_csv(fpath)
            dfs.append(df_i)
    df = pd.concat(dfs, ignore_index=True)
    feat_cols = [c for c in df.columns if c not in ['Phase', 'source']]
    X_hd = df[feat_cols].values.astype(np.float64)
    y_raw = df['Phase'].values
    phase_map = {'D': 0, 'P': 1, 'S': 2, 'H': 3, 'R': 4}
    phase_names = ['D (Rest)', 'P (Preparation)', 'S (Stroke)', 'H (Hold)', 'R (Retraction)']
    clusters = np.array([phase_map.get(l, 0) for l in y_raw])
    return X_hd, clusters, {
        "name": "Gesture Phase Segmentation",
        "N": len(X_hd), "features": X_hd.shape[1],
        "n_classes": 5,
        "class_names": phase_names,
        "label_col": "Phase",
    }


def load_mnist():
    import sklearn.datasets
    import sklearn.decomposition
    SEED = 40
    N_SAMPLES = 5000
    mnist = sklearn.datasets.fetch_openml('mnist_784', version=1,
                                           as_frame=False, parser='auto')
    X_full = mnist.data.astype(np.float64) / 255.0
    y_full = mnist.target.astype(int)
    rng = np.random.RandomState(SEED)
    idx = []
    for digit in range(10):
        digit_idx = np.where(y_full == digit)[0]
        chosen = rng.choice(digit_idx, size=N_SAMPLES // 10, replace=False)
        idx.extend(chosen)
    idx = np.array(idx)
    X_hd = X_full[idx]
    y_raw = y_full[idx]
    clusters = y_raw.copy()
    return X_hd, clusters, {
        "name": "MNIST Handwritten Digits",
        "N": len(X_hd), "features": X_hd.shape[1],
        "n_classes": 10,
        "class_names": [str(i) for i in range(10)],
        "label_col": "digit",
    }


def load_satellite():
    data_dir = os.path.join(DATASET_BASE,
        "8_Statlog/statlog+landsat+satellite")
    trn = pd.read_csv(os.path.join(data_dir, "sat.trn"), header=None, sep=' ')
    tst = pd.read_csv(os.path.join(data_dir, "sat.tst"), header=None, sep=' ')
    df = pd.concat([trn, tst], ignore_index=True)
    X_hd = df.iloc[:, :36].values.astype(np.float64)
    y_raw = df.iloc[:, 36].values.astype(int)
    class_names_map = {
        1: 'Red soil', 2: 'Cotton crop', 3: 'Grey soil',
        4: 'Damp grey soil', 5: 'Soil w/ vegetation', 7: 'Very damp grey soil'
    }
    unique_classes = sorted(class_names_map.keys())
    label_to_idx = {cls: i for i, cls in enumerate(unique_classes)}
    clusters = np.array([label_to_idx[y] for y in y_raw])
    return X_hd, clusters, {
        "name": "Statlog Landsat Satellite",
        "N": len(X_hd), "features": X_hd.shape[1],
        "n_classes": len(unique_classes),
        "class_names": [f"{c}: {class_names_map[c]}" for c in unique_classes],
        "label_col": "class",
    }


def load_theorem():
    data_dir = os.path.join(DATASET_BASE,
        "9_First_order_theorem_proving/first+order+theorem+proving/ml-prove")
    dfs = []
    for fname in ['train.csv', 'test.csv', 'validation.csv']:
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            dfs.append(pd.read_csv(fpath, header=None))
    df = pd.concat(dfs, ignore_index=True)
    X_hd = df.iloc[:, :56].values.astype(np.float64)
    y_raw = df.iloc[:, 56].values.astype(int)
    label_to_idx = {-1: 0, 1: 1}
    clusters = np.array([label_to_idx[y] for y in y_raw])
    return X_hd, clusters, {
        "name": "First-Order Theorem Proving",
        "N": len(X_hd), "features": X_hd.shape[1],
        "n_classes": 2,
        "class_names": ["Not Proved", "Proved"],
        "label_col": "class",
    }


def load_waveform():
    data_dir = os.path.join(DATASET_BASE,
        "10_waveform/waveform+database+generator+version+1")
    data_path = os.path.join(data_dir, "waveform.data")
    z_path = data_path + ".Z"
    if not os.path.exists(data_path) and os.path.exists(z_path):
        shutil.copy(z_path, data_path + ".Z")
        subprocess.run(['uncompress', data_path + ".Z"], capture_output=True)
    df = pd.read_csv(data_path, header=None)
    X_hd = df.iloc[:, :21].values.astype(np.float64)
    y_raw = df.iloc[:, 21].values.astype(int)
    clusters = y_raw.copy()
    return X_hd, clusters, {
        "name": "Waveform Database",
        "N": len(X_hd), "features": X_hd.shape[1],
        "n_classes": 3,
        "class_names": ["Class 0", "Class 1", "Class 2"],
        "label_col": "class",
    }


def load_isolet():
    import sklearn.decomposition
    data_dir = os.path.join(DATASET_BASE, "11_Isolet/isolet")
    SEED = 40

    dfs = []
    for fname in ['isolet1+2+3+4.data', 'isolet5.data']:
        fpath = os.path.join(data_dir, fname)
        z_path = fpath + ".Z"
        if not os.path.exists(fpath) and os.path.exists(z_path):
            shutil.copy(z_path, fpath + ".Z")
            subprocess.run(['uncompress', fpath + ".Z"], capture_output=True)
        if os.path.exists(fpath):
            dfs.append(pd.read_csv(fpath, header=None))
    df = pd.concat(dfs, ignore_index=True)
    X_raw = df.iloc[:, :617].values.astype(np.float64)
    y_raw = df.iloc[:, 617].values.astype(float)

    pca = sklearn.decomposition.PCA(n_components=50, random_state=SEED)
    X_hd = pca.fit_transform(X_raw)

    unique_classes = [float(i + 1) for i in range(26)]
    label_to_idx = {float(i + 1): i for i in range(26)}
    clusters = np.array([label_to_idx[y] for y in y_raw])
    letters = [chr(65 + i) for i in range(26)]
    return X_hd, clusters, {
        "name": "ISOLET Spoken Letter Recognition",
        "N": len(X_hd), "features": X_hd.shape[1],
        "n_classes": 26,
        "class_names": letters,
        "label_col": "letter",
        "pca_applied": True,
        "original_features": 617,
    }

def load_digits_sklearn():
    from sklearn import datasets
    d = datasets.load_digits()
    return d.data.astype(np.float64), d.target, {
        "name": "Digits (sklearn)",
        "N": len(d.data), "features": d.data.shape[1],
        "n_classes": 10,
        "class_names": [str(i) for i in range(10)],
        "label_col": "digit",
    }

def load_iris_sklearn():
    from sklearn import datasets
    d = datasets.load_iris()
    return d.data.astype(np.float64), d.target, {
        "name": "Iris (sklearn)",
        "N": len(d.data), "features": d.data.shape[1],
        "n_classes": 3,
        "class_names": list(d.target_names),
        "label_col": "species",
    }

def load_wine_sklearn():
    from sklearn import datasets
    d = datasets.load_wine()
    return d.data.astype(np.float64), d.target, {
        "name": "Wine (sklearn)",
        "N": len(d.data), "features": d.data.shape[1],
        "n_classes": 3,
        "class_names": list(d.target_names),
        "label_col": "class",
    }

# ── Registry ──────────────────────────────────────────────────────────────────
DATASET_REGISTRY = {
    
    "anuran_calls":  {
        "label": "Anuran Calls (7,195 × 22, 10 species)",
        "loader": load_anuran_calls,
        "group": "Biological",
    },
    "ccpp": {
        "label": "CCPP Power Plant (9,568 × 4, 5 PE bins)",
        "loader": load_ccpp,
        "group": "Engineering",
    },
    "musk_v2": {
        "label": "Musk v2 (6,598 × 166, 2 classes)",
        "loader": load_musk_v2,
        "group": "Chemical",
    },
    "spambase": {
        "label": "Spambase (4,601 × 57, 2 classes)",
        "loader": load_spambase,
        "group": "Text",
    },
    "gesture": {
        "label": "Gesture Phase (9,873 × 32, 5 phases)",
        "loader": load_gesture,
        "group": "Motion",
    },
    "mnist": {
        "label": "MNIST (5,000 × 784, 10 digits)",
        "loader": load_mnist,
        "group": "Image",
    },
    "satellite": {
        "label": "Landsat Satellite (6,435 × 36, 6 classes)",
        "loader": load_satellite,
        "group": "Remote Sensing",
    },
    "theorem": {
        "label": "Theorem Proving (6,118 × 56, 2 classes)",
        "loader": load_theorem,
        "group": "Logic",
    },
    "waveform": {
        "label": "Waveform (5,000 × 21, 3 classes)",
        "loader": load_waveform,
        "group": "Signal",
    },
    "isolet": {
        "label": "ISOLET (7,797 × 617→50 PCA, 26 letters)",
        "loader": load_isolet,
        "group": "Speech",
    },
    "digits": {
        "label": "Digits sklearn (1,797 × 64, 10 classes) ★ fast test",
        "loader": load_digits_sklearn,
        "group": "Testing",
    },
    "iris": {
        "label": "Iris sklearn (150 × 4, 3 classes) ★ fast test",
        "loader": load_iris_sklearn,
        "group": "Testing",
    },
    "wine": {
        "label": "Wine sklearn (178 × 13, 3 classes) ★ fast test",
        "loader": load_wine_sklearn,
        "group": "Testing",
    },
}


def get_dataset_list():
    return [
        {"id": k, "label": v["label"], "group": v["group"]}
        for k, v in DATASET_REGISTRY.items()
    ]


def load_dataset(dataset_id: str):
    if dataset_id not in DATASET_REGISTRY:
        raise ValueError(f"Unknown dataset: {dataset_id}")
    return DATASET_REGISTRY[dataset_id]["loader"]()
