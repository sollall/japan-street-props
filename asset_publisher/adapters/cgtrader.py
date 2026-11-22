"""CGTrader（Inbound API v1）。下書きを作成し、ファイルと画像を添付する。

https://api.cgtrader.com/docs/overview.html
注意: 下書き作成時のフィールド名は、実際に使う前に API ドキュメントで確認すること。
      ここでは更新 API（PUT /v1/models/{id}）の例にある title / description / prices を使っている。
"""

from __future__ import annotations

from .base import Adapter, Context, Result, env

API = "https://api.cgtrader.com/v1"


class CGTrader(Adapter):
    name = "cgtrader"
    kind = "api"
    default_formats = ["blend", "fbx", "glb", "usd", "stl"]
    env_vars = ["CGTRADER_ACCESS_TOKEN"]

    def check(self, listing, cfg, live):
        errors = super().check(listing, cfg, live)
        if "usd" not in listing.price:
            errors.append("price.usd がありません")
        if live and not cfg.get("category_id"):
            errors.append("publish.yaml の cgtrader.category_id を設定してください")
        return errors

    def _headers(self, ctx: Context) -> dict:
        return {"Authorization": f"Bearer {env('CGTRADER_ACCESS_TOKEN', ctx.dry_run)}"}

    def _body(self, ctx: Context) -> dict:
        lst = ctx.listing
        body = {
            "title": lst.text("title", "en", self.name),
            "description": lst.text("description", "en", self.name),
            "tags": lst.tags,
            "prices": {"download": f"{lst.price.get('usd', 0):.2f}"},
        }
        if ctx.cfg.get("category_id"):
            body["category_id"] = ctx.cfg["category_id"]
        return body

    def _attach(self, ctx: Context, model_id: str) -> None:
        for img in ctx.listing.images:
            ctx.transport.http("POST", f"{API}/models/{model_id}/images",
                               headers=self._headers(ctx), files={"image": img})
        ctx.transport.http("POST", f"{API}/models/{model_id}/files",
                           headers=self._headers(ctx), files={"file": ctx.package})

    def create(self, ctx: Context) -> Result:
        res = ctx.transport.http("POST", f"{API}/models", headers=self._headers(ctx), json=self._body(ctx))
        model_id = str(res.get("id") or ("DRYRUN" if ctx.dry_run else ""))
        if not model_id:
            raise RuntimeError(f"CGTrader の応答にIDがありません: {res}")
        self._attach(ctx, model_id)
        note = "CGTrader の My Products で内容を確認して公開してください"
        if ctx.listing.ai_usage != "none":
            # API での AI 申告方法は未確認のため、公開前に画面で申告する
            note += "（AI 使用の申告を画面で行うこと）"
        return Result(status="draft", remote_id=model_id, note=note)

    def update(self, ctx: Context, previous: dict) -> Result:
        model_id = previous["remote_id"]
        ctx.transport.http("PUT", f"{API}/models/{model_id}", headers=self._headers(ctx), json=self._body(ctx))
        ctx.transport.http("POST", f"{API}/models/{model_id}/files",
                           headers=self._headers(ctx), files={"file": ctx.package})
        return Result(status="updated", remote_id=model_id,
                      note="新しいファイルを追加しました。古いファイルは画面で削除してください")
