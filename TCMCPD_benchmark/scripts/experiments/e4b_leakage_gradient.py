#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E4b: split leakage across a capacity gradient.

The paper's original leakage result compared two models (naive Bayes, LightGBM), which is
enough to show that the inflation is not uniform but not enough to support the word
"capacity dependent". Here the same experiment is repeated for six model families that span
a wide range of effective capacity, with one shared label space and identical features, and
the inflation is related to how much signal each model extracts under the clean protocol.

Writes results/appendix/leakage_gradient.json
"""
import sys
sys.dont_write_bytecode = True

import json, os, time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.neural_network import MLPClassifier
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "TCMCPD_TCM_Case_Records_v1.0"
OUT = ROOT / "results" / "appendix"
OUT.mkdir(parents=True, exist_ok=True)

t0 = time.time()
pv = pd.read_csv(D / "relationships/patient_visit.csv")
vsym = pd.read_csv(D / "relationships/visit_symptom.csv")
vsyn = pd.read_csv(D / "relationships/visit_syndrome.csv")
v2p = dict(zip(pv.visit_id, pv.patient_id))
V2M, V2Y = defaultdict(set), defaultdict(set)
for v, s in vsym[["visit_id", "TCM_symptom_id"]].values:
    V2M[v].add(s)
for v, y in vsyn[["visit_id", "Syndrome_id"]].values:
    V2Y[v].add(y)
rows = [v for v in V2M if v in V2Y]
idx = {v: i for i, v in enumerate(rows)}

xv = [s for s, c in Counter(s for v in rows for s in V2M[v]).most_common() if c >= 5]
xi = {s: i for i, s in enumerate(xv)}
X = np.zeros((len(rows), len(xv)), np.float32)
for r, v in enumerate(rows):
    for s in V2M[v]:
        j = xi.get(s)
        if j is not None:
            X[r, j] = 1.0

pats = sorted({v2p[v] for v in rows})
pl = pats[:]
np.random.RandomState(42).shuffle(pl)
n = len(pl)
trp, tep = set(pl[:int(.7 * n)]), set(pl[int(.85 * n):])
itr_p = np.array([idx[v] for v in rows if v2p[v] in trp])
ite_p = np.array([idx[v] for v in rows if v2p[v] in tep])

perm = np.random.RandomState(7).permutation(len(rows))
itr_v = np.sort(perm[:int(.7 * len(rows))])
ite_v = np.sort(perm[int(.85 * len(rows)):])

yc = Counter(y for i in itr_p for y in V2Y[rows[i]])
yv = [y for y, c in yc.most_common() if c >= 30]
yi = {y: i for i, y in enumerate(yv)}
Y = np.zeros((len(rows), len(yv)), np.float32)
for r, v in enumerate(rows):
    for y in V2Y[v]:
        j = yi.get(y)
        if j is not None:
            Y[r, j] = 1.0
print("visits %d | features %d | shared labels %d" % (len(rows), len(xv), len(yv)), flush=True)


def ranks(S, Yt, ks=(1, 5, 10)):
    order = np.argsort(-S, axis=1)
    out = {}
    for k in ks:
        hit = np.take_along_axis(Yt, order[:, :k], axis=1)
        out["P@%d" % k] = float(hit.sum() / (k * len(Yt)))
        out["R@%d" % k] = float(hit.sum() / max(1.0, Yt.sum()))
    rel = np.take_along_axis(Yt, order[:, :10], axis=1)
    hits = np.cumsum(rel, axis=1)
    prec = hits / np.arange(1, 11)[None, :]
    den = rel.sum(1)
    ok = den > 0
    out["mAP@10"] = float(((prec * rel).sum(1)[ok] / den[ok]).mean())
    return out


def scores_nb(Xtr, Ytr, Xq):
    a = 1.0
    pos = Ytr.T @ Xtr
    n_pos = Ytr.sum(0) + 2 * a
    p = (pos + a) / (n_pos[:, None] + 2 * a)
    lp, l1p = np.log(p), np.log1p(-p)
    prior = (Ytr.sum(0) + 1.0) / (len(Ytr) + 2.0)
    return Xq @ (lp - l1p).T + l1p.sum(1)[None, :] + np.log(prior)[None, :]


def _positive_proba(model, Xq, n_labels):
    """sklearn returns a list of per-output arrays for multi-output models."""
    P = model.predict_proba(Xq)
    out = np.zeros((len(Xq), n_labels), np.float32)
    if isinstance(P, list):
        for j, pj in enumerate(P):
            out[:, j] = pj[:, 1] if pj.shape[1] > 1 else 0.0
    else:
        out[:, :] = P
    return out


def scores_knn(Xtr, Ytr, Xq, k=15):
    m = KNeighborsClassifier(n_neighbors=k, metric="cosine", weights="distance", n_jobs=8)
    m.fit(Xtr, Ytr)
    return _positive_proba(m, Xq, Ytr.shape[1])


def scores_mlp(Xtr, Ytr, Xq, seed=42):
    m = MLPClassifier(hidden_layer_sizes=(256,), max_iter=220, early_stopping=True,
                      n_iter_no_change=12, validation_fraction=0.12, random_state=seed)
    m.fit(Xtr, Ytr)
    return _positive_proba(m, Xq, Ytr.shape[1])


def scores_logreg(Xtr, Ytr, Xq):
    # single process on purpose: joblib memmapping fails on non-ASCII temp paths
    m = OneVsRestClassifier(LogisticRegression(max_iter=1000, C=1.0, solver="liblinear"))
    m.fit(Xtr, Ytr)
    return _positive_proba(m, Xq, Ytr.shape[1])


def scores_lgb(Xtr, Ytr, Xq):
    P = np.zeros((len(Xq), Ytr.shape[1]), np.float32)
    for j in range(Ytr.shape[1]):
        yj = Ytr[:, j]
        if yj.sum() < 3 or yj.sum() == len(yj):
            P[:, j] = yj.mean()
            continue
        m = lgb.LGBMClassifier(n_estimators=150, learning_rate=.08, num_leaves=31,
                               subsample=.9, colsample_bytree=.8, verbose=-1,
                               n_jobs=8, random_state=42)
        m.fit(Xtr, yj)
        P[:, j] = m.predict_proba(Xq)[:, 1]
    return P


def scores_labelgraph(Xtr, Ytr, Xq, seed=42):
    """MLP backbone + one step of label-graph propagation (co-occurrence adjacency)."""
    base = scores_mlp(Xtr, Ytr, Xq, seed=seed)
    C = Ytr.T @ Ytr
    np.fill_diagonal(C, 0.0)
    d = C.sum(1, keepdims=True)
    d[d == 0] = 1.0
    A = C / d
    return 0.65 * base + 0.35 * (base @ A)


MODELS = [("prior", None), ("NB", scores_nb), ("logistic", scores_logreg),
          ("kNN-15", scores_knn), ("MLP", scores_mlp), ("LightGBM", scores_lgb),
          ("MLP+label-graph", scores_labelgraph)]

res = {"data": {"visits": len(rows), "features": len(xv), "shared_labels": len(yv)}, "splits": {}}
for tag, itr, ite in (("patient_level", itr_p, ite_p), ("visit_level", itr_v, ite_v)):
    trset = {v2p[rows[i]] for i in itr}
    seen = float(np.mean([v2p[rows[i]] in trset for i in ite]))
    r = {"train": int(len(itr)), "test": int(len(ite)),
         "frac_test_visits_with_seen_patient": seen, "models": {}}
    for name, fn in MODELS:
        if name == "prior":
            S = np.tile(Y[itr].mean(0), (len(ite), 1))
        else:
            S = fn(X[itr], Y[itr], X[ite])
        r["models"][name] = ranks(S, Y[ite])
        print("[%s] %-16s %s" % (tag, name, {k: round(v, 3) for k, v in r["models"][name].items()}),
              flush=True)
    res["splits"][tag] = r
    print("   test visits with a seen patient: %.1f%%  (%.0fs)" % (100 * seen, time.time() - t0),
          flush=True)

trained = [m for m, f in MODELS if f is not None]
res["inflation"] = {}
for m in trained:
    res["inflation"][m] = {}
    for k in ("P@1", "R@5", "R@10", "mAP@10"):
        a = res["splits"]["visit_level"]["models"][m][k]
        b = res["splits"]["patient_level"]["models"][m][k]
        res["inflation"][m][k] = {"absolute": float(a - b),
                                 "relative_pct": float(100 * (a - b) / b) if b else None}

clean = [res["splits"]["patient_level"]["models"][m]["mAP@10"] for m in trained]
gaps = [res["inflation"][m]["mAP@10"]["relative_pct"] for m in trained]
rho, p = spearmanr(clean, gaps)
res["capacity_relation"] = {
    "proxy": "patient-level mAP@10 (signal the model extracts under the clean protocol)",
    "spearman_rho": float(rho), "p_value": float(p), "n_models": len(trained),
    "models_sorted_by_proxy": [m for _, m in sorted(zip(clean, trained))],
}
print("\nSpearman(clean mAP@10, relative mAP@10 inflation) = %.3f (p=%.4g, n=%d)"
      % (rho, p, len(trained)))
for m in sorted(trained, key=lambda m: res["splits"]["patient_level"]["models"][m]["mAP@10"]):
    print("   %-16s clean %.3f -> visit %.3f  %+6.1f%%"
          % (m, res["splits"]["patient_level"]["models"][m]["mAP@10"],
             res["splits"]["visit_level"]["models"][m]["mAP@10"],
             res["inflation"][m]["mAP@10"]["relative_pct"]))

res["elapsed_seconds"] = round(time.time() - t0, 1)
json.dump(res, open(OUT / "leakage_gradient.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nwrote results/appendix/leakage_gradient.json  (%.0fs)" % (time.time() - t0))
