"""
shared/config_loader.py
========================
Load the master YAML config from any module without hardcoding paths.

Usage:
    from shared.config_loader import load_config
    config = load_config()                          # auto-finds config/kharif2024.yaml
    config = load_config("config/kharif2024.yaml")  # explicit path
"""

import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default config path relative to repo root
DEFAULT_CONFIG = "config/kharif2024.yaml"


def load_config(path: str = None) -> dict:
    """
    Load the master pipeline config YAML.
    Searches from the current working directory up to the repo root.
    """
    if path:
        config_path = Path(path)
    else:
        # Walk up from cwd to find the config file (handles running from any subdir)
        config_path = _find_config()

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Run scripts from the repo root: bah2026-ps6/"
        )

    with open(config_path) as f:
        config = yaml.safe_load(f)

    logger.info(f"Config loaded from {config_path}")
    return config


def _find_config(filename: str = DEFAULT_CONFIG) -> Path:
    """Walk up the directory tree to find the config file."""
    current = Path.cwd()
    for _ in range(5):  # max 5 levels up
        candidate = current / filename
        if candidate.exists():
            return candidate
        current = current.parent
    return Path(filename)  # fallback — will raise FileNotFoundError above
