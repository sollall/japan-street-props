"""assets/ にある実際の出品情報が、そのままリハーサル出品に通ることを確かめる。"""

from pathlib import Path

import pytest

from asset_publisher.config import load_config
from asset_publisher.listing import load_listing, validate_listing
from asset_publisher.runner import publish

ROOT = Path(__file__).resolve().parent.parent
LISTINGS = sorted((ROOT / "assets").glob("*/listing.yaml"))
EXPECTED = {"jp-vending-machine", "jp-utility-pole", "jp-curve-mirror", "jp-guardrail", "jp-signboard"}


def test_all_five_props_exist():
    assert {load_listing(p).id for p in LISTINGS} == EXPECTED


@pytest.mark.parametrize("path", LISTINGS, ids=lambda p: p.parent.name)
def test_listing_is_valid(path):
    listing = load_listing(path)
    assert validate_listing(listing) == []
    assert listing.title.get("ja") and listing.description.get("ja")
    assert {"usd", "jpy"} <= set(listing.price)
    assert {f.format for f in listing.files} == {"blend", "fbx", "glb"}
    for f in listing.files:
        assert f.path.stat().st_size > 1000, f"{f.path} が空に近い"
    glb = next(f.path for f in listing.files if f.format == "glb")
    assert glb.read_bytes()[:4] == b"glTF"
    for img in listing.images:
        assert img.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_rehearsal_publish_makes_kits(tmp_path):
    config = load_config(ROOT / "publish.yaml")
    config.out_dir = tmp_path / "out"
    config.state_file = tmp_path / "state.json"
    listings = [load_listing(p) for p in LISTINGS]
    outcomes = publish(config, listings, ["sketchfab", "fab", "booth"], live=False)
    assert len(outcomes) == len(LISTINGS) * 3
    assert all(o.ok for o in outcomes), [o.note for o in outcomes if not o.ok]
    for listing in listings:
        for target in ("fab", "booth"):
            kit = config.out_dir / listing.id / target
            assert (kit / "package.zip").is_file()
            assert (kit / "fields.md").is_file()
    assert not config.state_file.exists()   # リハーサルでは出品履歴を書かない
