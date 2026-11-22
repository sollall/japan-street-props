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
KNOWN = ["sketchfab", "cgtrader", "etsy", "itch", "fab", "booth", "cults"]


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
                     "json": kw.get("json"), "files": list((kw.get("files") or {}).keys())})
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
    assert resolve_enabled(config, KNOWN) == ["sketchfab", "fab", "booth"]


def test_only_overrides_config(work):
    config, _ = cfg_and_listing(work)
    assert resolve_enabled(config, KNOWN, only="etsy,fab") == ["etsy", "fab"]


def test_enable_and_disable(work):
    config, _ = cfg_and_listing(work)
    got = resolve_enabled(config, KNOWN, enable=["cgtrader"], disable=["booth", "sketchfab"])
    assert got == ["cgtrader", "fab"]


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


# ---------- CLI ----------

def test_cli_record_then_skip(work, capsys):
    lst = "examples/danchi_5f/listing.yaml"
    assert main(["record", lst, "fab", "--url", "https://www.fab.com/listings/abc"]) == 0
    assert main(["publish", lst, "--only", "fab", "--live"]) == 0
    assert "スキップ" in capsys.readouterr().out


def test_cli_returns_error_code(work):
    assert main(["publish", "examples/danchi_5f/listing.yaml", "--only", "etsy"]) == 1
