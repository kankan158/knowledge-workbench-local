from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any, Dict


DEFAULT_WORKSPACE_STATE: Dict[str, Any] = {
    "folders": [],
    "tags": [],
    "docMeta": {},
}


class WorkspaceStateStore:
    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def read_state(self) -> Dict[str, Any]:
        with self._lock:
            if not self.state_path.exists():
                return deepcopy(DEFAULT_WORKSPACE_STATE)

            try:
                raw = self.state_path.read_text(encoding="utf-8")
                payload = json.loads(raw) if raw.strip() else {}
            except (OSError, json.JSONDecodeError):
                payload = {}

            return self._normalize_state(payload)

    def update_state(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            current = self.read_state()
            for key in DEFAULT_WORKSPACE_STATE:
                if key in patch and patch[key] is not None:
                    current[key] = patch[key]
            self._write_state(current)
            return current

    def _write_state(self, state: Dict[str, Any]) -> None:
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _normalize_state(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized = deepcopy(DEFAULT_WORKSPACE_STATE)
        if isinstance(payload, dict):
            folders = payload.get("folders")
            tags = payload.get("tags")
            doc_meta = payload.get("docMeta")
            if isinstance(folders, list):
                normalized["folders"] = folders
            if isinstance(tags, list):
                normalized["tags"] = tags
            if isinstance(doc_meta, dict):
                normalized["docMeta"] = doc_meta
        return normalized