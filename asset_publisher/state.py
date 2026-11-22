"""出品履歴（どの販売先に、どのバージョンを、何のIDで出したか）。

同じバージョンを2回出品しないため、また2回目以降を「更新」として扱うために使う。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class State:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, dict[str, dict]] = {}
        if path.is_file():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    def get(self, asset_id: str, platform: str) -> dict | None:
        return self.data.get(asset_id, {}).get(platform)

    def put(self, asset_id: str, platform: str, **record) -> None:
        record["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.data.setdefault(asset_id, {})[platform] = {
            k: v for k, v in record.items() if v is not None
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
