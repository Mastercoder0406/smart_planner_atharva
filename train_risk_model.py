"""
train_risk_model.py  -  Train the edge-aware obstacle-risk model.
Run:  python train_risk_model.py        (re-run any time to include newly reported obstacles)

- Synthetic samples (50,000) follow ml_risk.synthetic_probability().
- Real community reports from database.db (table 'obstacles') are added as positives
  (weight REAL_WEIGHT) so the model gradually learns from real data.
- No class_weight: the output is used as a PROBABILITY multiplier, so it must be calibrated.
  Quality is reported with ROC-AUC and Brier score, not accuracy alone.
- Metrics are measured on a held-out synthetic split (real reports are too few to test on).
"""
import random
import sqlite3
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, brier_score_loss, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split

from ml_risk import FEATURES, MODEL_PATH, NEARBY_RADIUS_M, MAX_NEARBY, haversine_m, make_row, synthetic_probability

REAL_WEIGHT = 3.0
N_SYNTHETIC = 50000


def generate_synthetic(n=N_SYNTHETIC, seed=42):
    rnd = random.Random(seed)
    rows, y = [], []
    for _ in range(n):
        hour, dow = rnd.randint(0, 23), rnd.randint(0, 6)
        rc = rnd.choices(range(5), weights=[3, 4, 2, 1.5, 1])[0]
        nb = rnd.choices(range(MAX_NEARBY + 1), weights=[80, 12, 5, 3])[0]
        rows.append(make_row(hour, dow, rc, nb))
        y.append(1 if rnd.random() < synthetic_probability(hour, dow, rc, nb) else 0)
    return pd.DataFrame(rows, columns=FEATURES), np.array(y)


def load_real_reports(db_path="database.db"):
    try:
        conn = sqlite3.connect(db_path)
        reports = conn.execute("SELECT lat, lng, reported_at FROM obstacles").fetchall()
        conn.close()
    except Exception:
        return pd.DataFrame(columns=FEATURES)
    rows = []
    for lat, lng, ts in reports:
        t = datetime.fromtimestamp(ts)
        near = sum(1 for la, ln, ts2 in reports
                   if (la, ln, ts2) != (lat, lng, ts) and abs(ts2 - ts) <= 7 * 86400
                   and haversine_m(lat, lng, la, ln) <= NEARBY_RADIUS_M)
        rows.append(make_row(t.hour, t.weekday(), 1, min(near, MAX_NEARBY)))   # road class unknown -> 1
    return pd.DataFrame(rows, columns=FEATURES)


def train():
    X, y = generate_synthetic()
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    real = load_real_reports()
    Xfit = pd.concat([Xtr, real], ignore_index=True)
    yfit = np.concatenate([ytr, np.ones(len(real), dtype=int)])
    w = np.concatenate([np.ones(len(ytr)), np.full(len(real), REAL_WEIGHT)])

    model = LogisticRegression(max_iter=2000)
    model.fit(Xfit, yfit, sample_weight=w)

    p = model.predict_proba(Xte)[:, 1]
    pred = (p >= 0.15).astype(int)
    base_rate = float(yte.mean())
    metrics = {
        "samples_synthetic": int(len(X)), "real_reports_used": int(len(real)),
        "obstacle_rate": round(base_rate, 3),
        "roc_auc": round(float(roc_auc_score(yte, p)), 3),
        "brier": round(float(brier_score_loss(yte, p)), 4),
        "brier_baseline": round(float(brier_score_loss(yte, np.full(len(yte), base_rate))), 4),
        "accuracy": round(float(accuracy_score(yte, pred)), 3),
        "majority_baseline_accuracy": round(1 - base_rate, 3),
        "precision@0.15": round(float(precision_score(yte, pred, zero_division=0)), 3),
        "recall@0.15": round(float(recall_score(yte, pred, zero_division=0)), 3),
        "f1@0.15": round(float(f1_score(yte, pred, zero_division=0)), 3),
        "trained_at": datetime.now().isoformat(timespec="seconds"),
    }
    joblib.dump({"model": model, "features": FEATURES, "metrics": metrics}, MODEL_PATH)
    print("Saved", MODEL_PATH)
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    return model


if __name__ == "__main__":
    train()