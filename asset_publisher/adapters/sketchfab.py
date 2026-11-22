"""Sketchfab（Data API v3）。下書きでアップロードし、ブラウザで回せる3Dプレビューとして使う。

https://sketchfab.com/developers/data-api/v3
"""

from __future__ import annotations

from .base import Adapter, Context, Result, env

API = "https://api.sketchfab.com/v3"


class Sketchfab(Adapter):
    name = "sketchfab"
    kind = "api"
    default_formats = ["glb"]
    env_vars = ["SKETCHFAB_API_TOKEN"]

    def formats(self, cfg: dict) -> list[str]:
        return [cfg.get("model_format", "glb")]

    def check(self, listing, cfg, live):
        errors = super().check(listing, cfg, live)
        if len(listing.tags) > 42:
            errors.append("Sketchfab のタグは42個までです")
        return errors

    def _headers(self, ctx: Context) -> dict:
        return {"Authorization": f"Token {env('SKETCHFAB_API_TOKEN', ctx.dry_run)}"}

    def _meta(self, ctx: Context) -> dict:
        lst = ctx.listing
        return {
            "name": lst.text("title", "en", self.name)[:48],
            "description": lst.text("description", "en", self.name),
            "tags": [t.lower().replace(" ", "-")[:48] for t in lst.tags],
            "isPublished": "true" if ctx.cfg.get("publish") else "false",
        }

    def create(self, ctx: Context) -> Result:
        model = ctx.listing.files_for(self.formats(ctx.cfg))[0].path
        res = ctx.transport.http(
            "POST", f"{API}/models",
            headers=self._headers(ctx), data=self._meta(ctx), files={"modelFile": model},
        )
        uid = res.get("uid") or ("DRYRUN" if ctx.dry_run else None)
        return Result(
            status="draft" if not ctx.cfg.get("publish") else "published",
            remote_id=uid,
            url=f"https://sketchfab.com/models/{uid}" if uid else None,
            note="処理完了後、画面で3D表示の設定を調整してから公開してください",
        )

    def update(self, ctx: Context, previous: dict) -> Result:
        # API で差し替えられるのは情報だけ。モデルファイルを変えたときは新規アップロードにする
        uid = previous["remote_id"]
        ctx.transport.http("PATCH", f"{API}/models/{uid}", headers=self._headers(ctx), data=self._meta(ctx))
        return Result(
            status="updated", remote_id=uid, url=previous.get("url"),
            note="Sketchfab は情報のみ更新しました（モデルファイルを差し替えるなら --force で新規作成）",
        )
