"""Etsy（Open API v3）。ダウンロード商品の下書きを作り、画像とファイルを添付する。

https://developer.etsy.com/documentation/tutorials/listings
"""

from __future__ import annotations

from .base import Adapter, Context, Result, env

API = "https://api.etsy.com/v3/application"


class Etsy(Adapter):
    name = "etsy"
    kind = "api"
    default_formats = ["stl", "3mf", "obj"]
    env_vars = ["ETSY_API_KEY", "ETSY_ACCESS_TOKEN"]

    def check(self, listing, cfg, live):
        errors = super().check(listing, cfg, live)
        cur = cfg.get("currency", "usd")
        if cur not in listing.price:
            errors.append(f"price.{cur} がありません")
        if len(listing.tags) > 13:
            errors.append("Etsy のタグは13個までです")
        if any(len(t) > 20 for t in listing.tags):
            errors.append("Etsy のタグは1つ20文字までです")
        if len(listing.text("title", "en", self.name)) > 140:
            errors.append("Etsy のタイトルは140文字までです")
        if live and not (cfg.get("shop_id") and cfg.get("taxonomy_id")):
            errors.append("publish.yaml の etsy.shop_id と etsy.taxonomy_id を設定してください")
        return errors

    def _headers(self, ctx: Context) -> dict:
        return {
            "x-api-key": env("ETSY_API_KEY", ctx.dry_run),
            "Authorization": f"Bearer {env('ETSY_ACCESS_TOKEN', ctx.dry_run)}",
        }

    def _fields(self, ctx: Context) -> dict:
        lst, cfg = ctx.listing, ctx.cfg
        return {
            "quantity": 999,
            "title": lst.text("title", "en", self.name),
            "description": lst.text("description", "en", self.name),
            "price": lst.price[cfg.get("currency", "usd")],
            "who_made": cfg.get("who_made", "i_did"),
            "when_made": cfg.get("when_made", "made_to_order"),
            "taxonomy_id": cfg.get("taxonomy_id"),
            "type": "download",
            "tags": ",".join(lst.tags),
        }

    def _shop(self, ctx: Context) -> str:
        return f"{API}/shops/{ctx.cfg.get('shop_id') or '<shop_id>'}"

    def create(self, ctx: Context) -> Result:
        res = ctx.transport.http("POST", f"{self._shop(ctx)}/listings",
                                 headers=self._headers(ctx), data=self._fields(ctx))
        listing_id = str(res.get("listing_id") or ("DRYRUN" if ctx.dry_run else ""))
        if not listing_id:
            raise RuntimeError(f"Etsy の応答に listing_id がありません: {res}")
        base = f"{self._shop(ctx)}/listings/{listing_id}"
        for rank, img in enumerate(ctx.listing.images[:10], start=1):
            ctx.transport.http("POST", f"{base}/images", headers=self._headers(ctx),
                               data={"rank": rank}, files={"image": img})
        ctx.transport.http("POST", f"{base}/files", headers=self._headers(ctx),
                           data={"name": ctx.package.name}, files={"file": ctx.package})
        return Result(status="draft", remote_id=listing_id,
                      url=f"https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}",
                      note="Etsy の下書きを確認して公開してください")

    def update(self, ctx: Context, previous: dict) -> Result:
        listing_id = previous["remote_id"]
        fields = {k: v for k, v in self._fields(ctx).items() if k not in ("quantity", "type")}
        ctx.transport.http("PATCH", f"{self._shop(ctx)}/listings/{listing_id}",
                           headers=self._headers(ctx), data=fields)
        ctx.transport.http("POST", f"{self._shop(ctx)}/listings/{listing_id}/files",
                           headers=self._headers(ctx), data={"name": ctx.package.name},
                           files={"file": ctx.package})
        return Result(status="updated", remote_id=listing_id, url=previous.get("url"),
                      note="新しいファイルを追加しました。古いファイルは画面で削除してください")
