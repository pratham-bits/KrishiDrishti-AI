"""
Random Forest / XGBoost Training Script — Repo 1: Crop Type Mapping

Usage:
    python models/train_rf.py --config configs/kharif2024.yaml
"""

import argparse
import json
import logging
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, classification_report,
                             cohen_kappa_score, confusion_matrix, f1_score)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CROP_NAMES = {0: "Rice", 1: "Maize", 2: "Cotton"}


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_and_clean_data(config: dict) -> tuple:
    """Load processed feature CSV, drop metadata and cloud flag columns."""
    df = pd.read_csv("data/processed/kharif2024_features.csv")
    logger.info(f"Loaded {len(df)} samples, {df.shape[1]} columns")

    # Remove unknown/background pixels
    df = df[df["crop_label"] >= 0]

    # Drop columns not used as features
    drop_cols = config["features"]["drop_cols"] + config["features"]["cloud_cols"]
    X = df.drop(columns=["crop_label"] + drop_cols, errors="ignore")
    y = df["crop_label"].values

    logger.info(f"Feature matrix: {X.shape} | Class distribution: {dict(zip(*np.unique(y, return_counts=True)))}")
    return X, y, X.columns.tolist()


def train(config: dict):
    X, y, feature_names = load_and_clean_data(config)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=config["model"]["test_size"],
        random_state=config["model"]["random_state"],
        stratify=y
    )

    # Random Forest (no scaling needed — tree-based)
    model = RandomForestClassifier(
        n_estimators=config["model"]["n_estimators"],
        max_depth=config["model"]["max_depth"],
        min_samples_leaf=config["model"]["min_samples_leaf"],
        n_jobs=config["model"]["n_jobs"],
        random_state=config["model"]["random_state"],
        class_weight="balanced"
    )

    logger.info(f"Training RandomForest with {config['model']['n_estimators']} trees...")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    # ─── METRICS ───
    oa = accuracy_score(y_test, y_pred)
    kappa = cohen_kappa_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="weighted")
    cm = confusion_matrix(y_test, y_pred).tolist()
    per_class_report = classification_report(
        y_test, y_pred,
        target_names=[CROP_NAMES[i] for i in sorted(CROP_NAMES.keys())],
        output_dict=True
    )

    logger.info(f"Overall Accuracy: {oa:.4f}")
    logger.info(f"Cohen Kappa: {kappa:.4f}")
    logger.info(f"Weighted F1: {f1:.4f}")

    if oa < 0.85:
        logger.warning("OA below 85% target. Consider: more training samples, feature engineering, or XGBoost.")

    # ─── SAVE MODEL ───
    Path(config["output"]["model_path"]).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, config["output"]["model_path"])
    logger.info(f"Model saved to {config['output']['model_path']}")

    # ─── SAVE METRICS ───
    metrics = {
        "overall_accuracy": round(oa, 4),
        "kappa_coefficient": round(kappa, 4),
        "weighted_f1": round(f1, 4),
        "confusion_matrix": cm,
        "per_class_report": per_class_report,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "feature_importances": dict(zip(feature_names,
                                        model.feature_importances_.round(4).tolist()))
    }
    Path(config["output"]["metrics_path"]).parent.mkdir(parents=True, exist_ok=True)
    with open(config["output"]["metrics_path"], "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Metrics saved to {config['output']['metrics_path']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/kharif2024.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    train(config)


if __name__ == "__main__":
    main()
