"""Roblox Creator Store（Open Cloud）。モデルを非公開でアップロードし、指定があれば出品まで行う。

アップロード: Assets API v1          https://create.roblox.com/docs/cloud/guides/usage-assets
出品・価格:   Creator Store Products  https://create.roblox.com/docs/cloud/reference/CreatorStoreProduct

流れ:
  1. モデル（既定は fbx）を POST /assets/v1/assets で送る。応答は operation なので、終わるまで問い合わせる
  2. previews: true なら、プレビュー画像を Image アセットとして上げ、モデルのプレビューに設定する
  3. distribute: true のときだけ、Creator Store の商品を作って公開する（既定は false = 非公開のまま）

2・3 が失敗してもモデルのアップロードは済んでいるので、エラーにはせずメモに残す
（エラーにすると履歴が残らず、次の実行で同じモデルを二重に作ってしまうため）。
"""

from __future__ import annotations

import json
import time

from .base import Adapter, Context, Result, env

ASSETS = "https://apis.roblox.com/assets/v1"
PRODUCTS = "https://apis.roblox.com/cloud/v2/creator-store-products"

MAX_BYTES = 20 * 1024 * 1024      # Assets API の1回あたりの上限
MAX_DESCRIPTION = 1000
MAX_NAME = 50
MAX_PREVIEWS = 5
PRICE_MIN, PRICE_MAX = 2.99, 49.99   # モデルの価格の範囲（USD）。0 は無料

MODEL_TYPES = {
    "fbx": "model/fbx",
    "glb": "model/gltf-binary",
    "gltf": "model/gltf+json",
    "rbxm": "model/x-rbxm",
    "rbxmx": "model/x-rbxm",
}
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".bmp": "image/bmp",
    ".tga": "image/tga",
}


class Roblox(Adapter):
    name = "roblox"
    kind = "api"
    default_formats = ["fbx"]
    env_vars = ["ROBLOX_API_KEY"]

    def formats(self, cfg: dict) -> list[str]:
        return [cfg.get("model_format", "fbx")]

    # ---------- 事前チェック ----------

    def check(self, listing, cfg, live):
        errors = super().check(listing, cfg, live)
        fmt = self.formats(cfg)[0]
        if fmt not in MODEL_TYPES:
            errors.append(f"Roblox が受け付けるのは {', '.join(MODEL_TYPES)} です（model_format: {fmt}）")
        for f in listing.files_for([fmt])[:1]:
            if f.path.is_file() and f.path.stat().st_size > MAX_BYTES:
                errors.append(f"Roblox へ送れるのは1ファイル 20MB までです: {f.path.name}")
        if len(listing.text("description", "en", self.name)) > MAX_DESCRIPTION:
            errors.append(f"Roblox の説明は {MAX_DESCRIPTION} 文字までです（overrides.roblox.description で短くできます）")
        if live and bool(cfg.get("user_id")) == bool(cfg.get("group_id")):
            errors.append("publish.yaml の roblox.user_id か roblox.group_id のどちらか一方を設定してください")
        if cfg.get("distribute"):
            price = listing.price.get("usd")
            if price is None:
                errors.append("price.usd がありません")
            elif price != 0 and not PRICE_MIN <= price <= PRICE_MAX:
                errors.append(f"Roblox のモデルの価格は ${PRICE_MIN}〜${PRICE_MAX}（または無料の 0）です")
        return errors

    # ---------- 共通の部品 ----------

    def _headers(self, ctx: Context) -> dict:
        return {"x-api-key": env("ROBLOX_API_KEY", ctx.dry_run)}

    def _creator(self, ctx: Context) -> dict:
        if ctx.cfg.get("group_id"):
            return {"groupId": int(ctx.cfg["group_id"])}
        return {"userId": int(ctx.cfg.get("user_id") or 0)}

    def _meta(self, ctx: Context) -> dict:
        lst = ctx.listing
        return {
            "displayName": lst.text("title", "en", self.name)[:MAX_NAME],
            "description": lst.text("description", "en", self.name),
        }

    def _model(self, ctx: Context):
        f = ctx.listing.files_for(self.formats(ctx.cfg))[0]
        return f.path, MODEL_TYPES[f.format.lower()]

    def _wait(self, ctx: Context, res: dict) -> dict:
        """operation が終わるまで問い合わせ、できあがったアセットの情報を返す。"""
        if ctx.dry_run:
            return {"assetId": "DRYRUN"}
        path = str(res.get("path", ""))
        if not path.startswith("operations/"):
            return res                                   # 情報だけの更新は、その場で結果が返る
        interval = float(ctx.cfg.get("poll_interval", 2))
        deadline = time.monotonic() + float(ctx.cfg.get("poll_timeout", 300))
        while not res.get("done"):
            if time.monotonic() > deadline:
                raise RuntimeError(f"Roblox の処理が時間内に終わりませんでした（{path}）")
            time.sleep(interval)
            res = ctx.transport.http("GET", f"{ASSETS}/{path}", headers=self._headers(ctx))
        if res.get("error"):
            raise RuntimeError(f"Roblox の処理が失敗しました: {res['error']}")
        return res.get("response") or {}

    def _upload(self, ctx: Context, asset_type: str, meta: dict, path, content_type: str) -> str:
        request = {"assetType": asset_type, **meta, "creationContext": {"creator": self._creator(ctx)}}
        res = ctx.transport.http(
            "POST", f"{ASSETS}/assets", headers=self._headers(ctx),
            data={"request": json.dumps(request, ensure_ascii=False)},
            files={"fileContent": (path, content_type)},
        )
        asset_id = str(self._wait(ctx, res).get("assetId") or "")
        if not asset_id:
            raise RuntimeError(f"Roblox の応答にアセットIDがありません: {res}")
        return asset_id

    # ---------- プレビュー画像・出品 ----------

    def _set_previews(self, ctx: Context, asset_id: str) -> str:
        """プレビュー画像を上げてモデルに設定する。戻り値はメモに足す文（成功なら空）。"""
        images = [p for p in ctx.listing.images if p.suffix.lower() in IMAGE_TYPES][:MAX_PREVIEWS]
        if not images:
            return ""
        title = self._meta(ctx)["displayName"]
        try:
            previews = []
            for i, img in enumerate(images, start=1):
                meta = {"displayName": f"{title[:MAX_NAME - 4]} #{i}", "description": f"Preview {i} of {title}"}
                image_id = self._upload(ctx, "Image", meta, img, IMAGE_TYPES[img.suffix.lower()])
                previews.append({"asset": f"assets/{image_id}", "altText": f"{title} ({i})"})
            ctx.transport.http(
                "PATCH", f"{ASSETS}/assets/{asset_id}?updateMask=previews", headers=self._headers(ctx),
                data={"request": json.dumps({"assetId": _as_int(asset_id), "previews": previews}, ensure_ascii=False)},
                multipart=True,
            )
        except Exception as e:  # noqa: BLE001  モデル本体は上がっているので止めない
            return f" / プレビュー画像の設定に失敗（画面で追加してください）: {e}"
        return ""

    def _distribute(self, ctx: Context, asset_id: str) -> str:
        """Creator Store に出品する。戻り値は失敗したときのメモ（成功なら空）。"""
        cents = round(ctx.listing.price.get("usd", 0) * 100)
        # 価格は significand × 10^-9 で表す決まり（$4.99 → 4990000000）。無料は 0 / 0
        quantity = {"significand": cents * 10_000_000, "exponent": -9} if cents else {"significand": 0, "exponent": 0}
        try:
            ctx.transport.http("POST", PRODUCTS, headers=self._headers(ctx), json={
                "modelAssetId": asset_id,
                "basePrice": {"currencyCode": "USD", "quantity": quantity},
                "published": True,
            })
        except Exception as e:  # noqa: BLE001
            return f" / Creator Store への出品に失敗（画面で出品してください）: {e}"
        return ""

    # ---------- 新規・更新 ----------

    def create(self, ctx: Context) -> Result:
        path, content_type = self._model(ctx)
        asset_id = self._upload(ctx, "Model", self._meta(ctx), path, content_type)
        configure = f"https://create.roblox.com/dashboard/creations/store/{asset_id}/configure"

        note = ""
        if ctx.cfg.get("previews", True):
            note += self._set_previews(ctx, asset_id)
        if ctx.cfg.get("distribute"):
            failed = self._distribute(ctx, asset_id)
            if not failed:
                return Result(status="published", remote_id=asset_id,
                              url=f"https://create.roblox.com/store/asset/{asset_id}",
                              note="Creator Store に出品しました" + note)
            note += failed
        return Result(
            status="draft", remote_id=asset_id, url=configure,
            note="非公開でアップロードしました。Creator Hub の Configure 画面で"
                 "「Distribute on Creator Store」をオンにし、価格を設定してください" + note,
        )

    def update(self, ctx: Context, previous: dict) -> Result:
        asset_id = previous["remote_id"]
        path, content_type = self._model(ctx)
        request = {"assetType": "Model", "assetId": _as_int(asset_id), **self._meta(ctx),
                   "creationContext": {"creator": self._creator(ctx)}}
        # 中身を差し替えられるのは fbx だけ。それ以外の形式は名前と説明だけ更新する
        replace = path.suffix.lower() == ".fbx"
        res = ctx.transport.http(
            "PATCH", f"{ASSETS}/assets/{asset_id}?updateMask=description%2CdisplayName",
            headers=self._headers(ctx),
            data={"request": json.dumps(request, ensure_ascii=False)},
            files={"fileContent": (path, content_type)} if replace else None,
            multipart=True,
        )
        self._wait(ctx, res)
        note = ("モデルを新しいバージョンに差し替えました" if replace
                else "名前と説明だけ更新しました（fbx 以外は中身を差し替えられません。--force で新規作成）")
        return Result(status="updated", remote_id=asset_id, url=previous.get("url"),
                      note=note + "。価格や出品状態を変える場合は Creator Hub の画面で行ってください")


def _as_int(asset_id: str):
    return int(asset_id) if str(asset_id).isdigit() else asset_id
