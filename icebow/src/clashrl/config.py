"""Configuration loading with nested-key access and project-relative paths."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class Config:
    data: Dict[str, Any]
    root: Path

    @classmethod
    def load(cls, path: Optional[str | os.PathLike] = None) -> "Config":
        # project root is …/icebow  (this file lives at src/clashrl/config.py)
        root = Path(__file__).resolve().parents[2]
        cfg_path = Path(path) if path else root / "config" / "config.yaml"
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(data=data, root=root)

    def get(self, *keys: str, default: Any = None) -> Any:
        """Fetch a nested value, e.g. cfg.get("record", "fps")."""
        node: Any = self.data
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def path(self, *parts: str) -> Path:
        """Resolve a path relative to the project root."""
        return self.root.joinpath(*parts)
