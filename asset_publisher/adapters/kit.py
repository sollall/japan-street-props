"""API がない販売先（Fab / BOOTH / Cults3D）向けの「手作業用キット」。

出力するもの:
  package.zip   その販売先が受け付ける形式だけをまとめた zip
  images/       プレビュー画像（掲載順に番号付き）
  fields.md     入力欄ごとにコピペできる文面
  checklist.md  出品前の確認項目

出品が終わったら `asset-publisher record <listing> <販売先> --url <URL>` で記録すると、
次回からは「更新」として扱われる。
"""

from __future__ import annotations

import shutil

from .base import Adapter, Context, Result

AI_LABEL = {
    "none": {"en": "No AI tools were used.", "ja": "AIツールは使用していません。"},
    "assisted": {"en": "AI tools were used in parts of the workflow (e.g. modeling scripts).",
                 "ja": "制作工程の一部（モデリング用スクリプト作成など）にAIツールを使用しています。"},
    "generated": {"en": "This asset was generated with AI tools.",
                  "ja": "このアセットはAIツールで生成しています。"},
}


class KitAdapter(Adapter):
    kind = "kit"
    upload_hint = ""
    currency = "usd"
    extra_checks: list[str] = []

    def _price(self, ctx: Context) -> str:
        p = ctx.listing.price.get(self.currency)
        if p is None:
            return "（未設定）"
        return f"¥{int(p):,}" if self.currency == "jpy" else f"${p:.2f}"

    def _checklist(self, ctx: Context) -> list[str]:
        items = [
            f"出品画面を開く: {self.upload_hint}",
            "package.zip をアップロードした",
            "images/ の画像を番号順に登録した",
            "fields.md の各項目を入力した",
            f"価格を {self._price(ctx)} にした",
        ]
        if ctx.listing.ai_usage != "none":
            items.append("AI 使用の申告をした（fields.md の「AI 使用」を参照）")
        items += self.extra_checks
        items.append(f"出品後: asset-publisher record {ctx.listing.source} {self.name} --url <出品ページのURL>")
        return items

    def create(self, ctx: Context) -> Result:
        out = ctx.out_dir
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ctx.package, out / "package.zip")

        img_dir = out / "images"
        if img_dir.exists():
            shutil.rmtree(img_dir)
        img_dir.mkdir()
        for i, img in enumerate(ctx.listing.images, start=1):
            shutil.copy2(img, img_dir / f"{i:02d}_{img.name}")

        lst, lang = ctx.listing, self.lang
        tags = lst.tags
        fields = [
            f"# {self.name} 入力用（{lst.id} v{lst.version}）",
            "",
            "## タイトル", "", lst.text("title", lang, self.name), "",
            "## 説明", "", lst.text("description", lang, self.name), "",
            "## タグ", "", ", ".join(tags), "",
            "## 価格", "", self._price(ctx), "",
            "## ライセンス", "", lst.license, "",
            "## AI 使用", "", AI_LABEL[lst.ai_usage][lang],
        ]
        (out / "fields.md").write_text("\n".join(fields) + "\n", encoding="utf-8")
        (out / "checklist.md").write_text(
            f"# {self.name} 出品チェックリスト\n\n" + "\n".join(f"- [ ] {c}" for c in self._checklist(ctx)) + "\n",
            encoding="utf-8",
        )
        return Result(status="kit_ready", note=f"キットを作成: {out}")

    def update(self, ctx: Context, previous: dict) -> Result:
        result = self.create(ctx)
        result.remote_id = previous.get("remote_id")
        result.url = previous.get("url")
        result.note += "（既存の出品ページでファイルを差し替えてください）"
        return result


class Fab(KitAdapter):
    name = "fab"
    lang = "en"
    default_formats = ["blend", "fbx", "glb", "usd"]
    upload_hint = "fab.com にログイン → 上部ツールバーの「公開」→ 新しい出品を作成"
    extra_checks = [
        "AI を使った場合は 'CreatedWithAI' タグを付けた（部分的な使用も対象）",
        "審査に出した（承認されるまで公開されない）",
    ]


class Booth(KitAdapter):
    name = "booth"
    lang = "ja"
    currency = "jpy"
    default_formats = ["blend", "fbx", "glb", "usd", "stl"]
    upload_hint = "BOOTH のショップ管理 → 商品管理 → 新しく商品を登録"
    extra_checks = [
        "商品種別を「ダウンロード商品」にした",
        "利用規約（再配布禁止・商用利用の範囲）を説明文に入れた",
    ]


class Cults(KitAdapter):
    name = "cults"
    lang = "en"
    default_formats = ["stl", "3mf", "obj"]
    upload_hint = "cults3d.com の「アップロード」→「3Dモデルを追加」"
    extra_checks = ["AI を使った場合は AI 生成の申告欄にチェックした"]
