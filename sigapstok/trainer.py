"""Epoch-based ML + statistical hyperparameter training with anti-overfitting regularization."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from sigapstok.forecasting import (
    classify_demand_pattern,
    forecast_damped_holt,
    forecast_sba,
    forecast_ses,
)
from sigapstok.synthetic_data import build_synthetic_rsud_skus


@dataclass
class TrainingSummary:
    epochs: int
    final_train_loss: float
    final_val_loss: float
    best_val_loss: float
    best_epoch: int
    epoch_history: list[dict[str, float]]
    optimized_stat_params: dict[str, dict[str, float]]
    blend_weights: dict[str, float]
    test_metrics: dict[str, dict[str, float]]


def _extend_history_36m(skus: list[dict], seed: int = 99) -> list[dict]:
    """Generate 36 months of realistic seasonal + pattern-consistent history per SKU."""
    rng = np.random.default_rng(seed)
    extended = []
    for s in skus:
        hist = []
        for m in range(36):
            season = 1.15 if (m % 12 in (2, 7, 8)) else (0.92 if (m % 12 in (4, 5)) else 1.0)
            if rng.random() > s["p_nonzero"]:
                hist.append(0.0)
                continue
            base = s["base"] * season
            if s["pattern"] == "SMOOTH":
                val = max(1.0, round(float(rng.normal(base, base * 0.12))))
            elif s["pattern"] == "ERRATIC":
                val = max(1.0, round(float(rng.normal(base, base * 0.48))))
            elif s["pattern"] == "INTERMITTENT":
                val = max(1.0, round(float(rng.normal(base, base * 0.18))))
            else:  # LUMPY
                val = max(1.0, round(float(base * rng.uniform(0.4, 2.5))))
            hist.append(val)
        item = dict(s)
        item["history_36m"] = hist
        extended.append(item)
    return extended


def _extract_features(window: list[float], month_idx: int, ven: str) -> np.ndarray:
    """Build normalized feature vector from 6-month lag window + trend, pattern & seasonality cues."""
    w = np.array(window[-6:], dtype=np.float64)
    scale = max(1.0, float(np.mean(w)) + float(np.std(w)))
    norm_lags = w / scale

    nonzero = w[w > 0]
    zero_ratio = float(np.mean(w == 0))
    adi = float(len(w) / max(1, len(nonzero)))
    mean_nz = float(np.mean(nonzero)) if len(nonzero) > 0 else 0.0
    cv2 = float(np.var(nonzero) / (mean_nz ** 2)) if len(nonzero) > 1 and mean_nz > 0 else 0.0

    # Linear trend slope over last 6 months (normalized)
    x_idx = np.arange(len(w), dtype=np.float64)
    x_centered = x_idx - np.mean(x_idx)
    slope = float(np.sum(x_centered * norm_lags) / max(1e-6, np.sum(x_centered ** 2)))

    # Exponentially weighted ratio
    ses_ratio = forecast_ses(w.tolist(), alpha=0.35) / scale

    sin_m = math.sin(2.0 * math.pi * (month_idx % 12) / 12.0)
    cos_m = math.cos(2.0 * math.pi * (month_idx % 12) / 12.0)
    ven_v = 1.0 if ven == "V" else 0.0
    ven_e = 1.0 if ven == "E" else 0.0

    return np.array(
        [
            *norm_lags.tolist(),
            float(np.mean(w[-3:]) / scale),
            ses_ratio,
            slope,
            zero_ratio,
            min(adi / 6.0, 1.0),
            min(cv2 / 2.0, 1.0),
            sin_m,
            cos_m,
            ven_v,
            ven_e,
        ],
        dtype=np.float64,
    )


class PureNumpyMLP:
    """Compact 2-layer MLP with Dropout, L2 weight decay, and Adam optimizer to prevent overfitting."""

    def __init__(self, input_dim: int, hidden_dim: int = 12, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.w1 = rng.normal(0.0, math.sqrt(2.0 / input_dim), size=(input_dim, hidden_dim))
        self.b1 = np.zeros((1, hidden_dim), dtype=np.float64)
        self.w2 = rng.normal(0.0, math.sqrt(2.0 / hidden_dim), size=(hidden_dim, 1))
        self.b2 = np.zeros((1, 1), dtype=np.float64)

        self._params = [self.w1, self.b1, self.w2, self.b2]
        self._m = [np.zeros_like(p) for p in self._params]
        self._v = [np.zeros_like(p) for p in self._params]
        self._t = 0

    def forward(
        self,
        x: np.ndarray,
        dropout_rate: float = 0.0,
        rng: np.random.Generator | None = None,
    ) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray | None]]:
        z1 = x @ self.w1 + self.b1
        a1 = np.maximum(0.0, z1)  # ReLU
        mask = None
        if dropout_rate > 0.0 and rng is not None:
            keep = 1.0 - dropout_rate
            mask = (rng.random(a1.shape) < keep).astype(np.float64) / keep
            a1 = a1 * mask
        out = np.maximum(0.0, a1 @ self.w2 + self.b2)
        return out, (z1, a1, mask)

    def predict(self, x: np.ndarray) -> np.ndarray:
        out, _ = self.forward(x, dropout_rate=0.0, rng=None)
        return out.ravel()

    def train_step(
        self,
        x: np.ndarray,
        y: np.ndarray,
        lr: float = 0.006,
        l2_reg: float = 2e-3,
        dropout_rate: float = 0.20,
        rng: np.random.Generator | None = None,
    ) -> float:
        n = x.shape[0]
        y_col = y.reshape(-1, 1)
        out, (z1, a1, mask) = self.forward(x, dropout_rate=dropout_rate, rng=rng)
        diff = out - y_col
        delta = 0.5
        abs_d = np.abs(diff)
        loss_vec = np.where(abs_d <= delta, 0.5 * diff ** 2, delta * (abs_d - 0.5 * delta))
        reg_loss = 0.5 * l2_reg * (np.sum(self.w1 ** 2) + np.sum(self.w2 ** 2))
        loss = float(np.mean(loss_vec) + reg_loss)

        d_out = np.where(abs_d <= delta, diff, delta * np.sign(diff)) / n
        d_out = d_out * (out > 0).astype(np.float64)

        dw2 = a1.T @ d_out + l2_reg * self.w2
        db2 = np.sum(d_out, axis=0, keepdims=True)
        da1 = d_out @ self.w2.T
        if mask is not None:
            da1 = da1 * mask
        dz1 = da1 * (z1 > 0).astype(np.float64)
        dw1 = x.T @ dz1 + l2_reg * self.w1
        db1 = np.sum(dz1, axis=0, keepdims=True)

        grads = [dw1, db1, dw2, db2]
        self._t += 1
        beta1, beta2, eps = 0.9, 0.999, 1e-8
        for idx, (param, grad) in enumerate(zip(self._params, grads)):
            self._m[idx] = beta1 * self._m[idx] + (1.0 - beta1) * grad
            self._v[idx] = beta2 * self._v[idx] + (1.0 - beta2) * (grad ** 2)
            m_hat = self._m[idx] / (1.0 - beta1 ** self._t)
            v_hat = self._v[idx] / (1.0 - beta2 ** self._t)
            param -= lr * m_hat / (np.sqrt(v_hat) + eps)

        return loss

    def get_weights(self) -> dict[str, list]:
        return {
            "w1": self.w1.tolist(),
            "b1": self.b1.tolist(),
            "w2": self.w2.tolist(),
            "b2": self.b2.tolist(),
        }

    def load_weights(self, data: dict[str, list]) -> None:
        self.w1 = np.array(data["w1"], dtype=np.float64)
        self.b1 = np.array(data["b1"], dtype=np.float64)
        self.w2 = np.array(data["w2"], dtype=np.float64)
        self.b2 = np.array(data["b2"], dtype=np.float64)
        self._params = [self.w1, self.b1, self.w2, self.b2]


def _stat_predict_with_params(history: list[float], pattern: str, params: dict[str, dict[str, float]]) -> float:
    if pattern == "SMOOTH":
        return forecast_ses(history, alpha=params["SMOOTH"]["alpha"])
    if pattern == "ERRATIC":
        p = params["ERRATIC"]
        return forecast_damped_holt(history, alpha=p["alpha"], beta=p["beta"], phi=p["phi"])
    if pattern in ("INTERMITTENT", "LUMPY"):
        return forecast_sba(history, alpha=params[pattern]["alpha"])
    return 0.0


def _compute_error_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(math.sqrt(np.mean((y_true - y_pred) ** 2)))
    denom = np.abs(y_true) + np.abs(y_pred)
    smape_terms = np.zeros_like(denom, dtype=np.float64)
    np.divide(2.0 * np.abs(y_true - y_pred), denom, out=smape_terms, where=denom > 1e-6)
    smape = float(np.mean(smape_terms) * 100.0)
    sum_y = float(np.sum(np.abs(y_true)))
    wape = (float(np.sum(np.abs(y_true - y_pred))) / sum_y * 100.0) if sum_y > 0 else 0.0
    accuracy_pct = round(max(0.0, 100.0 - wape), 2)
    return {
        "MAE": round(mae, 2),
        "RMSE": round(rmse, 2),
        "sMAPE_pct": round(smape, 2),
        "WAPE_pct": round(wape, 2),
        "Accuracy_pct": accuracy_pct,
    }


def train_and_evaluate_models(
    epochs: int = 200,
    seed: int = 42,
    save_artifact_path: str | Path | None = None,
) -> TrainingSummary:
    """
    Train regularized 2-layer MLP (Dropout + L2 + Cosine LR + Early Stopping) and
    pattern-specific statistical smoothing parameters on 36-month rolling-origin splits.
    """
    base_skus = build_synthetic_rsud_skus(seed=seed)
    skus = _extend_history_36m(base_skus, seed=seed + 50)

    # 1. Rolling-origin split: Train (t=6..23), Val (t=24..29), Test (t=30..35)
    x_train, y_train = [], []
    x_val, y_val, scales_val, val_meta = [], [], [], []
    x_test, scales_test, test_meta = [], [], []

    for s in skus:
        hist = s["history_36m"]
        for t in range(6, 36):
            window = hist[:t]
            scale = max(1.0, float(np.mean(window[-6:])) + float(np.std(window[-6:])))
            feat = _extract_features(window, t, s["ven"])
            target_ratio = hist[t] / scale
            pattern, _, _ = classify_demand_pattern(window)

            meta = {"history": window, "target": hist[t], "pattern": pattern, "ven": s["ven"]}
            if t <= 23:
                x_train.append(feat)
                y_train.append(target_ratio)
            elif t <= 29:
                x_val.append(feat)
                y_val.append(target_ratio)
                scales_val.append(scale)
                val_meta.append(meta)
            else:
                x_test.append(feat)
                scales_test.append(scale)
                test_meta.append(meta)

    x_tr = np.vstack(x_train)
    y_tr = np.array(y_train, dtype=np.float64)
    x_va = np.vstack(x_val)
    y_va = np.array(y_val, dtype=np.float64)
    x_te = np.vstack(x_test)

    # 2. Epoch-based MLP training with Dropout, L2, Cosine LR decay, and Early Stopping
    mlp = PureNumpyMLP(input_dim=x_tr.shape[1], hidden_dim=12, seed=seed)
    best_val_loss = float("inf")
    best_epoch = 0
    best_weights = mlp.get_weights()
    epoch_history: list[dict[str, float]] = []

    rng = np.random.default_rng(seed)
    lr_max, lr_min = 0.006, 0.0004
    for ep in range(1, epochs + 1):
        lr = lr_min + 0.5 * (lr_max - lr_min) * (1.0 + math.cos(math.pi * ep / epochs))
        perm = rng.permutation(len(x_tr))
        tr_loss = mlp.train_step(
            x_tr[perm],
            y_tr[perm],
            lr=lr,
            l2_reg=2e-3,
            dropout_rate=0.20,
            rng=rng,
        )

        val_pred = mlp.predict(x_va)
        val_diff = val_pred - y_va
        val_loss = float(np.mean(0.5 * np.where(np.abs(val_diff) <= 0.5, val_diff ** 2, 0.5 * (2 * np.abs(val_diff) - 0.5))))

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = ep
            best_weights = mlp.get_weights()

        if ep == 1 or ep % 25 == 0 or ep == epochs:
            epoch_history.append(
                {
                    "epoch": ep,
                    "train_loss": round(tr_loss, 5),
                    "val_loss": round(val_loss, 5),
                }
            )

    mlp.load_weights(best_weights)

    # 3. Fine-grained statistical hyperparameter optimization on validation set
    optimized_stat_params: dict[str, dict[str, float]] = {
        "SMOOTH": {"alpha": 0.35},
        "ERRATIC": {"alpha": 0.35, "beta": 0.15, "phi": 0.85},
        "INTERMITTENT": {"alpha": 0.15},
        "LUMPY": {"alpha": 0.15},
    }

    smooth_val = [m for m in val_meta if m["pattern"] == "SMOOTH"]
    if smooth_val:
        best_a, best_e = 0.35, float("inf")
        for a in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.45, 0.55]:
            err = sum(abs(m["target"] - forecast_ses(m["history"], alpha=a)) for m in smooth_val)
            if err < best_e:
                best_e, best_a = err, a
        optimized_stat_params["SMOOTH"] = {"alpha": best_a}

    erratic_val = [m for m in val_meta if m["pattern"] == "ERRATIC"]
    if erratic_val:
        best_p, best_e = (0.30, 0.10, 0.80), float("inf")
        for a in [0.15, 0.25, 0.35, 0.45]:
            for b in [0.05, 0.10, 0.15]:
                for phi in [0.70, 0.80, 0.90]:
                    err = sum(abs(m["target"] - forecast_damped_holt(m["history"], a, b, phi)) for m in erratic_val)
                    if err < best_e:
                        best_e, best_p = err, (a, b, phi)
        optimized_stat_params["ERRATIC"] = {"alpha": best_p[0], "beta": best_p[1], "phi": best_p[2]}

    for pat in ("INTERMITTENT", "LUMPY"):
        pat_val = [m for m in val_meta if m["pattern"] == pat]
        if pat_val:
            best_a, best_e = 0.15, float("inf")
            for a in [0.05, 0.08, 0.12, 0.15, 0.20, 0.25, 0.35]:
                err = sum(abs(m["target"] - forecast_sba(m["history"], alpha=a)) for m in pat_val)
                if err < best_e:
                    best_e, best_a = err, a
            optimized_stat_params[pat] = {"alpha": best_a}

    # 4. Learn pattern-specific ensemble blend weights on validation set
    val_mlp_preds = mlp.predict(x_va) * np.array(scales_val)
    blend_weights: dict[str, float] = {}
    for pat in ("SMOOTH", "ERRATIC", "INTERMITTENT", "LUMPY", "NO_DEMAND"):
        idxs = [i for i, m in enumerate(val_meta) if m["pattern"] == pat]
        if not idxs:
            blend_weights[pat] = 0.35
            continue
        best_w, best_mae = 0.0, float("inf")
        for w in [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.65, 0.80, 1.0]:
            tot_err = 0.0
            for i in idxs:
                stat_p = _stat_predict_with_params(val_meta[i]["history"], pat, optimized_stat_params)
                comb = w * float(val_mlp_preds[i]) + (1.0 - w) * stat_p
                tot_err += abs(val_meta[i]["target"] - comb)
            if tot_err < best_mae:
                best_mae, best_w = tot_err, w
        blend_weights[pat] = best_w

    # 5. Evaluate on HELD-OUT TEST SET (Months 30-35)
    y_test_true = np.array([m["target"] for m in test_meta], dtype=np.float64)
    test_mlp_preds = mlp.predict(x_te) * np.array(scales_test)

    pred_rsud = np.array([1.10 * m["history"][-1] for m in test_meta], dtype=np.float64)
    pred_amc3 = np.array([sum(m["history"][-3:]) / 3.0 for m in test_meta], dtype=np.float64)

    default_params = {
        "SMOOTH": {"alpha": 0.35},
        "ERRATIC": {"alpha": 0.35, "beta": 0.15, "phi": 0.85},
        "INTERMITTENT": {"alpha": 0.15},
        "LUMPY": {"alpha": 0.15},
    }
    pred_stat_untrained = np.array(
        [_stat_predict_with_params(m["history"], m["pattern"], default_params) for m in test_meta],
        dtype=np.float64,
    )
    pred_hybrid_trained = np.array(
        [
            blend_weights.get(m["pattern"], 0.35) * float(test_mlp_preds[i])
            + (1.0 - blend_weights.get(m["pattern"], 0.35))
            * _stat_predict_with_params(m["history"], m["pattern"], optimized_stat_params)
            for i, m in enumerate(test_meta)
        ],
        dtype=np.float64,
    )

    test_metrics = {
        "RSUD_1Mo_Plus_10Pct": _compute_error_metrics(y_test_true, pred_rsud),
        "Excel_3Mo_AMC": _compute_error_metrics(y_test_true, pred_amc3),
        "SigapStok_Untrained_Stat": _compute_error_metrics(y_test_true, pred_stat_untrained),
        "SigapStok_MLP_Only": _compute_error_metrics(y_test_true, test_mlp_preds),
        "SigapStok_Trained_Hybrid": _compute_error_metrics(y_test_true, pred_hybrid_trained),
    }

    if save_artifact_path is not None:
        artifact_path = Path(save_artifact_path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact = {
            "epochs": epochs,
            "best_epoch": best_epoch,
            "best_val_loss": round(best_val_loss, 5),
            "optimized_stat_params": optimized_stat_params,
            "blend_weights": blend_weights,
            "mlp_weights": best_weights,
            "test_metrics": test_metrics,
        }
        artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    return TrainingSummary(
        epochs=epochs,
        final_train_loss=epoch_history[-1]["train_loss"],
        final_val_loss=epoch_history[-1]["val_loss"],
        best_val_loss=round(best_val_loss, 5),
        best_epoch=best_epoch,
        epoch_history=epoch_history,
        optimized_stat_params=optimized_stat_params,
        blend_weights=blend_weights,
        test_metrics=test_metrics,
    )


def predict_with_trained_artifact(
    artifact: dict[str, Any],
    history: list[float],
    month_idx: int,
    ven_status: str,
) -> tuple[str, float]:
    """Produce a hybrid forecast for a single SKU using saved trained weights."""
    pattern, _, _ = classify_demand_pattern(history)
    stat_pred = _stat_predict_with_params(history, pattern, artifact["optimized_stat_params"])

    if len(history) < 6:
        padded = [0.0] * (6 - len(history)) + list(history)
    else:
        padded = list(history[-6:])
    scale = max(1.0, float(np.mean(padded)) + float(np.std(padded)))
    feat = _extract_features(padded, month_idx, ven_status).reshape(1, -1)

    mlp = PureNumpyMLP(input_dim=feat.shape[1], hidden_dim=12)
    mlp.load_weights(artifact["mlp_weights"])
    mlp_pred = float(mlp.predict(feat)[0]) * scale

    w = float(artifact["blend_weights"].get(pattern, 0.35))
    hybrid = max(0.0, w * mlp_pred + (1.0 - w) * stat_pred)
    return pattern, round(hybrid, 2)
