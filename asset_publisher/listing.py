"""listing.yaml（1アセット分の出品情報）の読み込みと共通チェック。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

AI_USAGE = ("none", "assisted", "generated")


@dataclass
class AssetFile:
    path: Path
    format: str


@dataclass
class Listing:
    source: Path
    id: str
    version: str
    title: dict[str, str]
    description: dict[str, str]
    tags: list[str]
    license: str
    ai_usage: str
    price: dict[str, float]
    files: list[AssetFile]
    images: list[Path]
    overrides: dict[str, dict] = field(default_factory=dict)

    @property
    def base_dir(self) -> Path:
        return self.source.parent

    def text(self, key: str, lang: str, platform: str | None = None) -> str:
        """タイトル・説明を取得。販売先の上書き → 指定言語 → 英語 の順に探す。"""
        if platform and key in self.overrides.get(platform, {}):
            return str(self.overrides[platform][key])
        values = getattr(self, key)
        return values.get(lang) or values.get("en") or ""

    def files_for(self, formats: list[str] | None) -> list[AssetFile]:
        if not formats:
            return list(self.files)
        wanted = {f.lower() for f in formats}
        return [f for f in self.files if f.format.lower() in wanted]


def load_listing(path: str | Path) -> Listing:
    path = Path(path)
    d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base = path.parent

    def as_lang(v) -> dict[str, str]:
        if isinstance(v, str):
            return {"en": v}
        return {k: str(s).strip() for k, s in (v or {}).items()}

    return Listing(
        source=path,
        id=str(d.get("id", "")),
        version=str(d.get("version", "")),
        title=as_lang(d.get("title")),
        description=as_lang(d.get("description")),
        tags=[str(t) for t in d.get("tags") or []],
        license=str(d.get("license", "")),
        ai_usage=str(d.get("ai_usage", "")),
        price={k: float(v) for k, v in (d.get("price") or {}).items()},
        files=[AssetFile(base / f["path"], str(f["format"])) for f in d.get("files") or []],
        images=[base / p for p in d.get("images") or []],
        overrides=d.get("overrides") or {},
    )


def validate_listing(listing: Listing) -> list[str]:
    """どの販売先でも必要な項目のチェック。問題点のリストを返す（空なら OK）。"""
    errors = []
    if not listing.id:
        errors.append("id がありません")
    if not listing.version:
        errors.append("version がありません")
    if not listing.title.get("en"):
        errors.append("英語のタイトル（title.en）がありません")
    if not listing.description.get("en"):
        errors.append("英語の説明（description.en）がありません")
    if listing.ai_usage not in AI_USAGE:
        errors.append(f"ai_usage は {' / '.join(AI_USAGE)} のどれかにしてください")
    if not listing.files:
        errors.append("files が空です")
    if not listing.images:
        errors.append("images が空です（プレビュー画像は最低1枚必要）")
    for f in listing.files:
        if not f.path.is_file():
            errors.append(f"ファイルがありません: {f.path}")
    for p in listing.images:
        if not p.is_file():
            errors.append(f"画像がありません: {p}")
    return errors
