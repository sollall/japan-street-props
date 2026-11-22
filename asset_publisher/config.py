"""publish.yaml の読み込みと、販売先のオン・オフの決定。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    path: Path
    state_file: Path
    out_dir: Path
    targets: dict[str, dict] = field(default_factory=dict)

    def target(self, name: str) -> dict:
        return self.targets.get(name, {})


def load_config(path: str | Path) -> Config:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base = path.parent
    targets = data.get("targets") or {}
    for name, cfg in targets.items():
        if cfg is None:
            targets[name] = {}
    return Config(
        path=path,
        state_file=base / data.get("state_file", ".publish-state.json"),
        out_dir=base / data.get("out_dir", "dist/publish"),
        targets=targets,
    )


def _split(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def resolve_enabled(
    config: Config,
    known: list[str],
    only: str | None = None,
    enable: list[str] | None = None,
    disable: list[str] | None = None,
) -> list[str]:
    """設定ファイル → --only（または環境変数 PUBLISH_ONLY）→ --enable → --disable の順に適用する。

    --only を指定すると、設定ファイルの enabled は無視してその販売先だけを対象にする。
    """
    enable = [e for item in (enable or []) for e in _split(item)]
    disable = [d for item in (disable or []) for d in _split(item)]
    only_list = _split(only) or _split(os.environ.get("PUBLISH_ONLY"))

    for name in [*only_list, *enable, *disable]:
        if name not in known:
            raise ValueError(f"不明な販売先: {name}（使えるのは {', '.join(known)}）")

    if only_list:
        selected = list(only_list)
    else:
        selected = [n for n in known if config.target(n).get("enabled", False)]

    for name in enable:
        if name not in selected:
            selected.append(name)
    selected = [n for n in selected if n not in disable]
    # 表示順を安定させる
    return [n for n in known if n in selected]
