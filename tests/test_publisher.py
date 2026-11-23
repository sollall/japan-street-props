"""実際の販売先には接続せず、送信内容と挙動を確認するテスト。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import requests

from asset_publisher.cli import main
from asset_publisher.config import load_config, resolve_enabled
from asset_publisher.listing import load_listing
from asset_publisher.runner import publish

ROOT = Path(__file__).resolve().parents[1]
KNOWN = ["sketchfab", "cgtrader", "etsy", "itch", "roblox", "fab", "booth", "cults"]


@pytest.fixture
def work(tmp_path, monkeypatch):
    """サンプル一式を一時ディレクトリにコピーして、その中で実行する。"""
    shutil.copy(ROOT / "publish.yaml", tmp_path / "publish.yaml")
    shutil.copytree(ROOT / "examples", tmp_path / "examples")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PUBLISH_ONLY", raising=False)
    return tmp_path


@pytest.fixture
def fake_http(monkeypatch):
    """requests を差し替えて、送信内容を記録し、販売先らしい応答を返す。"""
    sent = []

    class Resp:
        def __init__(self, status, body):
            self.status_code = status
            self._body = body
            self.content = json.dumps(body).encode()
            self.text = json.dumps(body)
            self.headers = {}

        def json(self):
            return self._body

    def fake_request(self, method, url, **kw):
        sent.append({"method": method, "url": url, "data": kw.get("data"),
                     "json": kw.get("json"), "files": list((kw.get("files") or {}).keys()),
                     "files_raw": kw.get("files")})
        if url.endswith("/assets/v1/assets") and method == "POST":
            n = sum(1 for x in sent if x["url"].endswith("/assets/v1/assets"))
            return Resp(200, {"path": f"operations/op{n}", "done": False})
        if "/assets/v1/operations/op" in url:
            return Resp(200, {"path": "operations/x", "done": True,
                              "response": {"assetId": str(9000 + int(url.rsplit("op", 1)[1]))}})
        if "creator-store-products" in url:
            return Resp(200, {"path": "creator-store-products/p1"})
        if "sketchfab" in url and method == "POST":
            return Resp(201, {"uid": "sf123"})
        if url.endswith("/v1/models") and method == "POST":
            return Resp(201, {"id": 555})
        if url.endswith("/listings") and method == "POST":
            return Resp(201, {"listing_id": 777})
        return Resp(200, {})

    monkeypatch.setattr(requests.Session, "request", fake_request)
    return sent


def cfg_and_listing(work):
    return load_config(work / "publish.yaml"), load_listing(work / "examples/danchi_5f/listing.yaml")


# ---------- オン・オフ ----------

def test_config_enabled_flags(work):
    config, _ = cfg_and_listing(work)
    assert resolve_enabled(config, KNOWN) == ["sketchfab", "cgtrader", "roblox", "fab", "booth"]


def test_only_overrides_config(work):
    config, _ = cfg_and_listing(work)
    assert resolve_enabled(config, KNOWN, only="etsy,fab") == ["etsy", "fab"]


def test_enable_and_disable(work):
    config, _ = cfg_and_listing(work)
    got = resolve_enabled(config, KNOWN, enable=["cgtrader"], disable=["booth", "sketchfab"])
    assert got == ["cgtrader", "roblox", "fab"]


def test_env_only(work, monkeypatch):
    config, _ = cfg_and_listing(work)
    monkeypatch.setenv("PUBLISH_ONLY", "itch")
    assert resolve_enabled(config, KNOWN) == ["itch"]


def test_unknown_target_rejected(work):
    config, _ = cfg_and_listing(work)
    with pytest.raises(ValueError):
        resolve_enabled(config, KNOWN, only="amazon")


# ---------- リハーサル ----------

def test_dry_run_sends_nothing_and_keeps_no_state(work, fake_http):
    config, listing = cfg_and_listing(work)
    outcomes = publish(config, [listing], ["sketchfab", "cgtrader", "fab"], live=False)
    assert all(o.ok for o in outcomes)
    assert fake_http == []                         # 1件も送っていない
    assert not config.state_file.exists()          # 履歴も残さない
    planned = [c.url for o in outcomes for c in o.calls]
    assert "https://api.sketchfab.com/v3/models" in planned


# ---------- 本番送信（モック） ----------

def test_live_creates_drafts_and_records_state(work, fake_http, monkeypatch):
    for v in ["SKETCHFAB_API_TOKEN", "CGTRADER_ACCESS_TOKEN"]:
        monkeypatch.setenv(v, "x")
    config, listing = cfg_and_listing(work)
    config.targets["cgtrader"]["category_id"] = 10

    outcomes = publish(config, [listing], ["sketchfab", "cgtrader", "fab"], live=True)
    assert [o.action for o in outcomes] == ["create", "create", "create"]

    sf = fake_http[0]
    assert sf["url"] == "https://api.sketchfab.com/v3/models"
    assert sf["data"]["isPublished"] == "false"    # 下書きで上げている
    assert sf["files"] == ["modelFile"]

    cg_urls = [s["url"] for s in fake_http if "cgtrader" in s["url"]]
    assert cg_urls[0].endswith("/v1/models")
    assert cg_urls.count("https://api.cgtrader.com/v1/models/555/images") == 4
    assert cg_urls[-1] == "https://api.cgtrader.com/v1/models/555/files"

    state = json.loads(config.state_file.read_text())
    assert state["danchi-5f"]["sketchfab"]["remote_id"] == "sf123"
    assert state["danchi-5f"]["cgtrader"]["remote_id"] == "555"
    assert state["danchi-5f"]["fab"]["status"] == "kit_ready"


def test_same_version_is_skipped_new_version_is_update(work, fake_http, monkeypatch):
    monkeypatch.setenv("SKETCHFAB_API_TOKEN", "x")
    config, listing = cfg_and_listing(work)
    publish(config, [listing], ["sketchfab"], live=True)

    again = publish(config, [listing], ["sketchfab"], live=True)
    assert again[0].action == "skip"

    listing.version = "1.1.0"
    upd = publish(config, [listing], ["sketchfab"], live=True)
    assert upd[0].action == "update"
    assert fake_http[-1]["method"] == "PATCH"
    assert fake_http[-1]["url"].endswith("/v3/models/sf123")


def test_force_recreates(work, fake_http, monkeypatch):
    monkeypatch.setenv("SKETCHFAB_API_TOKEN", "x")
    config, listing = cfg_and_listing(work)
    publish(config, [listing], ["sketchfab"], live=True)
    forced = publish(config, [listing], ["sketchfab"], live=True, force=True)
    assert forced[0].action == "create"


def test_missing_token_fails_only_that_target(work, fake_http, monkeypatch):
    monkeypatch.delenv("SKETCHFAB_API_TOKEN", raising=False)
    config, listing = cfg_and_listing(work)
    outcomes = publish(config, [listing], ["sketchfab", "fab"], live=True)
    assert outcomes[0].action == "error" and "SKETCHFAB_API_TOKEN" in outcomes[0].note
    assert outcomes[1].ok                          # 他の販売先は続行
    assert fake_http == []


def test_http_error_is_isolated(work, monkeypatch):
    monkeypatch.setenv("SKETCHFAB_API_TOKEN", "x")

    class Bad:
        status_code, content, text, headers = 500, b"", "server error", {}

    monkeypatch.setattr(requests.Session, "request", lambda *a, **k: Bad())
    config, listing = cfg_and_listing(work)
    outcomes = publish(config, [listing], ["sketchfab", "booth"], live=True)
    assert outcomes[0].action == "error" and "500" in outcomes[0].note
    assert outcomes[1].ok
    state = json.loads(config.state_file.read_text())
    assert "sketchfab" not in state["danchi-5f"]   # 失敗したものは記録しない


# ---------- 販売先ごとのチェック ----------

def test_etsy_rules(work):
    config, listing = cfg_and_listing(work)
    listing.tags = [f"tag{i}" for i in range(14)]
    out = publish(config, [listing], ["etsy"], live=False)
    assert out[0].action == "error"
    assert "13個" in out[0].note
    assert "受け付ける形式" in out[0].note        # STL が無いので Etsy には出せない


def test_package_contains_only_accepted_formats(work):
    import zipfile
    config, listing = cfg_and_listing(work)
    config.targets["sketchfab"]["enabled"] = False
    publish(config, [listing], ["fab"], live=False)
    names = zipfile.ZipFile(config.out_dir / "danchi-5f/fab/package.zip").namelist()
    assert "danchi-5f/danchi_5f.glb" in names and "danchi-5f/README.txt" in names


def test_kit_uses_japanese_for_booth(work):
    config, listing = cfg_and_listing(work)
    publish(config, [listing], ["booth"], live=False)
    fields = (config.out_dir / "danchi-5f/booth/fields.md").read_text(encoding="utf-8")
    assert "【3Dモデル】日本の団地" in fields and "¥2,800" in fields


# ---------- Roblox Creator Store ----------

@pytest.fixture
def roblox(work, fake_http, monkeypatch):
    monkeypatch.setenv("ROBLOX_API_KEY", "x")
    monkeypatch.setattr("asset_publisher.adapters.roblox.time.sleep", lambda s: None)
    config, listing = cfg_and_listing(work)
    config.targets["roblox"]["user_id"] = 1234567
    return config, listing, fake_http


def test_roblox_uploads_private_model_with_previews(roblox):
    config, listing, sent = roblox
    out = publish(config, [listing], ["roblox"], live=True)[0]
    assert out.action == "create" and out.status == "draft"
    assert out.url == "https://create.roblox.com/dashboard/creations/store/9001/configure"

    uploads = [s for s in sent if s["url"].endswith("/assets/v1/assets")]
    requests_sent = [json.loads(u["data"]["request"]) for u in uploads]
    assert [r["assetType"] for r in requests_sent] == ["Model"] + ["Image"] * 4
    assert requests_sent[0]["creationContext"] == {"creator": {"userId": 1234567}}
    assert all(u["files"] == ["fileContent"] for u in uploads)

    patch = [s for s in sent if s["method"] == "PATCH"][0]
    assert patch["url"].endswith("/assets/9001?updateMask=previews")
    previews = json.loads(patch["files_raw"]["request"][1])["previews"]
    assert [p["asset"] for p in previews] == [f"assets/{i}" for i in range(9002, 9006)]

    assert not any("creator-store-products" in s["url"] for s in sent)   # 出品はしていない
    state = json.loads(config.state_file.read_text())
    assert state["danchi-5f"]["roblox"]["remote_id"] == "9001"


def test_roblox_distribute_sets_usd_price(roblox):
    config, listing, sent = roblox
    config.targets["roblox"].update(distribute=True, previews=False)
    out = publish(config, [listing], ["roblox"], live=True)[0]
    assert out.status == "published" and out.url == "https://create.roblox.com/store/asset/9001"
    body = sent[-1]["json"]
    assert sent[-1]["url"].endswith("/cloud/v2/creator-store-products")
    assert body["modelAssetId"] == "9001" and body["published"] is True
    assert body["basePrice"]["quantity"] == {"significand": 19_990_000_000, "exponent": -9}


def test_roblox_distribute_failure_keeps_upload(roblox, monkeypatch):
    config, listing, sent = roblox
    config.targets["roblox"].update(distribute=True, previews=False)
    real = requests.Session.request

    def failing(self, method, url, **kw):
        if "creator-store-products" in url:
            class Bad:
                status_code, content, text, headers = 403, b"", "not a seller", {}
            return Bad()
        return real(self, method, url, **kw)

    monkeypatch.setattr(requests.Session, "request", failing)
    out = publish(config, [listing], ["roblox"], live=True)[0]
    assert out.ok and out.status == "draft" and "403" in out.note
    state = json.loads(config.state_file.read_text())
    assert state["danchi-5f"]["roblox"]["remote_id"] == "9001"   # 二重アップロードを防ぐため記録は残す


def test_roblox_update_replaces_fbx(roblox):
    config, listing, sent = roblox
    config.targets["roblox"]["previews"] = False
    publish(config, [listing], ["roblox"], live=True)
    listing.version = "1.1.0"
    out = publish(config, [listing], ["roblox"], live=True)[0]
    assert out.action == "update"
    patch = [s for s in sent if s["method"] == "PATCH"][-1]
    assert patch["url"].endswith("/assets/9001?updateMask=description%2CdisplayName")
    assert "fileContent" in patch["files"]
    assert len([s for s in sent if s["url"].endswith("/assets/v1/assets")]) == 1   # 新規作成はしていない


def test_roblox_checks(work, monkeypatch):
    monkeypatch.setenv("ROBLOX_API_KEY", "x")
    config, listing = cfg_and_listing(work)
    config.targets["roblox"]["distribute"] = True
    listing.price["usd"] = 99.0
    note = publish(config, [listing], ["roblox"], live=True)[0].note
    assert "user_id" in note and "$2.99" in note


def test_roblox_dry_run(work, fake_http):
    config, listing = cfg_and_listing(work)
    out = publish(config, [listing], ["roblox"], live=False)[0]
    assert out.ok and fake_http == []
    assert out.calls[0].url == "https://apis.roblox.com/assets/v1/assets"


# ---------- CLI ----------

def test_cli_record_then_skip(work, capsys):
    lst = "examples/danchi_5f/listing.yaml"
    assert main(["record", lst, "fab", "--url", "https://www.fab.com/listings/abc"]) == 0
    assert main(["publish", lst, "--only", "fab", "--live"]) == 0
    assert "スキップ" in capsys.readouterr().out


def test_cli_returns_error_code(work):
    assert main(["publish", "examples/danchi_5f/listing.yaml", "--only", "etsy"]) == 1
