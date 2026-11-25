"""Epoch-based ML + statistical hyperparameter training and evaluation for SigapStok."""

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


def _extend_history_24m(skus: list[dict], seed: int = 99) -> list[dict]:
    """Generate 24 months of realistic seasonal + pattern-consistent history per SKU."""
    rng = np.random.default_rng(seed)
    extended = []
    for s in skus:
        hist = []
        for m in range(24):
            # Seasonal bump around registration/monsoon peaks (months 2, 7, 8, 14, 19, 20)
            season = 1.15 if (m % 12 in (2, 7, 8)) else (0.92 if (m % 12 in (4, 5)) else 1.0)
            if rng.random() > s["p_nonzero"]:
                hist.append(0.0)
                continue
            base = s["base"] * season
            if s["pattern"] == "SMOOTH":
                val = max(1.0, round(float(rng.normal(base, base * 0.12))))
            elif s["pattern"] == "ERRATIC":
                val = max(1.0, round(float(rng.normal(base, base * 0.50))))
            elif s["pattern"] == "INTERMITTENT":
                val = max(1.0, round(float(rng.normal(base, base * 0.18))))
            else:  # LUMPY
                val = max(1.0, round(float(base * rng.uniform(0.4, 2.6))))
            hist.append(val)
        item = dict(s)
        item["history_24m"] = hist
        extended.append(item)
    return extended


def _extract_features(window: list[float], month_idx: int, ven: str) -> np.ndarray:
    """Build normalized feature vector from 6-month lag window + pattern & seasonality cues."""
    w = np.array(window[-6:], dtype=np.float64)
    scale = max(1.0, float(np.mean(w)) + float(np.std(w)))
    norm_lags = w / scale

    nonzero = w[w > 0]
    zero_ratio = float(np.mean(w == 0))
    adi = float(len(w) / max(1, len(nonzero)))
    mean_nz = float(np.mean(nonzero)) if len(nonzero) > 0 else 0.0
    cv2 = float(np.var(nonzero) / (mean_nz ** 2)) if len(nonzero) > 1 and mean_nz > 0 else 0.0

    sin_m = math.sin(2.0 * math.pi * (month_idx % 12) / 12.0)
    cos_m = math.cos(2.0 * math.pi * (month_idx % 12) / 12.0)
    ven_v = 1.0 if ven == "V" else 0.0
    ven_e = 1.0 if ven == "E" else 0.0

    return np.array(
        [
            *norm_lags.tolist(),
            float(np.mean(w[-3:]) / scale),
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
    """Two-layer MLP trained with Adam optimizer and L2 regularization in pure NumPy."""

    def __init__(self, input_dim: int, hidden_dim: int = 24, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.w1 = rng.normal(0.0, math.sqrt(2.0 / input_dim), size=(input_dim, hidden_dim))
        self.b1 = np.zeros((1, hidden_dim), dtype=np.float64)
        self.w2 = rng.normal(0.0, math.sqrt(2.0 / hidden_dim), size=(hidden_dim, 1))
        self.b2 = np.zeros((1, 1), dtype=np.float64)

        self._params = [self.w1, self.b1, self.w2, self.b2]
        self._m = [np.zeros_like(p) for p in self._params]
        self._v = [np.zeros_like(p) for p in self._params]
        self._t = 0

    def forward(self, x: np.ndarray) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray]]:
        z1 = x @ self.w1 + self.b1
        a1 = np.maximum(0.0, z1)  # ReLU
        out = np.maximum(0.0, a1 @ self.w2 + self.b2)  # Non-negative forecast ratio
        return out, (z1, a1)

    def predict(self, x: np.ndarray) -> np.ndarray:
        out, _ = self.forward(x)
        return out.ravel()

    def train_step(
        self,
        x: np.ndarray,
        y: np.ndarray,
        lr: float = 0.008,
        l2_reg: float = 1e-4,
    ) -> float:
        n = x.shape[0]
        y_col = y.reshape(-1, 1)
        out, (z1, a1) = self.forward(x)
        diff = out - y_col
        # Smooth L1 / Huber loss for robustness to erratic spikes
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
    # Normalized Accuracy = max(0, 100 - WAPE%) where WAPE = sum(|e|) / sum(y)
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
    epochs: int = 160,
    seed: int = 42,
    save_artifact_path: str | Path | None = None,
) -> TrainingSummary:
    """
    Train both pattern-specific statistical smoothing parameters and a pure-NumPy MLP,
    learn optimal pattern blend weights on validation windows, and benchmark accuracy on
    held-out test months (Months 19-24).
    """
    base_skus = build_synthetic_rsud_skus(seed=seed)
    skus = _extend_history_24m(base_skus, seed=seed + 50)

    # 1. Build rolling-origin train (t=6..14), val (t=15..18), test (t=19..23)
    x_train, y_train, scales_train = [], [], []
    x_val, y_val, scales_val, val_meta = [], [], [], []
    x_test, y_test, scales_test, test_meta = [], [], [], []

    for s in skus:
        hist = s["history_24m"]
        for t in range(6, 24):
            window = hist[:t]
            scale = max(1.0, float(np.mean(window[-6:])) + float(np.std(window[-6:])))
            feat = _extract_features(window, t, s["ven"])
            target_ratio = hist[t] / scale
            pattern, _, _ = classify_demand_pattern(window)

            meta = {"history": window, "target": hist[t], "pattern": pattern, "ven": s["ven"]}
            if t <= 14:
                x_train.append(feat)
                y_train.append(target_ratio)
                scales_train.append(scale)
            elif t <= 18:
                x_val.append(feat)
                y_val.append(target_ratio)
                scales_val.append(scale)
                val_meta.append(meta)
            else:
                x_test.append(feat)
                y_test.append(target_ratio)
                scales_test.append(scale)
                test_meta.append(meta)

    x_tr = np.vstack(x_train)
    y_tr = np.array(y_train, dtype=np.float64)
    x_va = np.vstack(x_val)
    y_va = np.array(y_val, dtype=np.float64)
    x_te = np.vstack(x_test)

    # 2. Epoch-based MLP training with validation early-stopping checkpoint
    mlp = PureNumpyMLP(input_dim=x_tr.shape[1], hidden_dim=24, seed=seed)
    best_val_loss = float("inf")
    best_epoch = 0
    best_weights = mlp.get_weights()
    epoch_history: list[dict[str, float]] = []

    rng = np.random.default_rng(seed)
    for ep in range(1, epochs + 1):
        perm = rng.permutation(len(x_tr))
        tr_loss = mlp.train_step(x_tr[perm], y_tr[perm], lr=0.008, l2_reg=2e-4)

        val_pred = mlp.predict(x_va)
        val_diff = val_pred - y_va
        val_loss = float(np.mean(0.5 * np.where(np.abs(val_diff) <= 0.5, val_diff ** 2, 0.5 * (2 * np.abs(val_diff) - 0.5))))

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = ep
            best_weights = mlp.get_weights()

        if ep == 1 or ep % 20 == 0 or ep == epochs:
            epoch_history.append(
                {
                    "epoch": ep,
                    "train_loss": round(tr_loss, 5),
                    "val_loss": round(val_loss, 5),
                }
            )

    mlp.load_weights(best_weights)

    # 3. Optimize statistical hyperparameters on validation windows per pattern
    optimized_stat_params: dict[str, dict[str, float]] = {
        "SMOOTH": {"alpha": 0.35},
        "ERRATIC": {"alpha": 0.35, "beta": 0.15, "phi": 0.85},
        "INTERMITTENT": {"alpha": 0.15},
        "LUMPY": {"alpha": 0.15},
    }

    # Tune SMOOTH alpha
    smooth_val = [m for m in val_meta if m["pattern"] == "SMOOTH"]
    if smooth_val:
        best_a, best_e = 0.35, float("inf")
        for a in [0.15, 0.25, 0.35, 0.45, 0.55]:
            err = sum(abs(m["target"] - forecast_ses(m["history"], alpha=a)) for m in smooth_val)
            if err < best_e:
                best_e, best_a = err, a
        optimized_stat_params["SMOOTH"] = {"alpha": best_a}

    # Tune ERRATIC damped holt
    erratic_val = [m for m in val_meta if m["pattern"] == "ERRATIC"]
    if erratic_val:
        best_p, best_e = (0.30, 0.10, 0.80), float("inf")
        for a in [0.20, 0.30, 0.40]:
            for b in [0.05, 0.15]:
                for phi in [0.75, 0.85, 0.95]:
                    err = sum(abs(m["target"] - forecast_damped_holt(m["history"], a, b, phi)) for m in erratic_val)
                    if err < best_e:
                        best_e, best_p = err, (a, b, phi)
        optimized_stat_params["ERRATIC"] = {"alpha": best_p[0], "beta": best_p[1], "phi": best_p[2]}

    # Tune INTERMITTENT & LUMPY SBA alpha
    for pat in ("INTERMITTENT", "LUMPY"):
        pat_val = [m for m in val_meta if m["pattern"] == pat]
        if pat_val:
            best_a, best_e = 0.15, float("inf")
            for a in [0.08, 0.12, 0.18, 0.25, 0.35]:
                err = sum(abs(m["target"] - forecast_sba(m["history"], alpha=a)) for m in pat_val)
                if err < best_e:
                    best_e, best_a = err, a
            optimized_stat_params[pat] = {"alpha": best_a}

    # 4. Learn pattern-specific ensemble blend weight (w_mlp * mlp + (1 - w_mlp) * stat) on validation set
    val_mlp_preds = mlp.predict(x_va) * np.array(scales_val)
    blend_weights: dict[str, float] = {}
    for pat in ("SMOOTH", "ERRATIC", "INTERMITTENT", "LUMPY", "NO_DEMAND"):
        idxs = [i for i, m in enumerate(val_meta) if m["pattern"] == pat]
        if not idxs:
            blend_weights[pat] = 0.35
            continue
        best_w, best_mae = 0.0, float("inf")
        for w in [0.0, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.0]:
            tot_err = 0.0
            for i in idxs:
                stat_p = _stat_predict_with_params(val_meta[i]["history"], pat, optimized_stat_params)
                comb = w * float(val_mlp_preds[i]) + (1.0 - w) * stat_p
                tot_err += abs(val_meta[i]["target"] - comb)
            if tot_err < best_mae:
                best_mae, best_w = tot_err, w
        blend_weights[pat] = best_w

    # 5. Evaluate all models on HELD-OUT TEST SET (Months 19-24)
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

    mlp = PureNumpyMLP(input_dim=feat.shape[1], hidden_dim=24)
    mlp.load_weights(artifact["mlp_weights"])
    mlp_pred = float(mlp.predict(feat)[0]) * scale

    w = float(artifact["blend_weights"].get(pattern, 0.35))
    hybrid = max(0.0, w * mlp_pred + (1.0 - w) * stat_pred)
    return pattern, round(hybrid, 2)
