"""itch.io（butler コマンド）。ファイルの更新だけを自動化する。ページは先に手で作っておく。

https://itch.io/docs/butler/pushing
"""

from __future__ import annotations

import os
import shutil

from .base import Adapter, Context, Result


class Itch(Adapter):
    name = "itch"
    kind = "api"
    default_formats = ["blend", "fbx", "glb", "usd"]
    env_vars = ["BUTLER_API_KEY"]

    def check(self, listing, cfg, live):
        errors = super().check(listing, cfg, live)
        project = cfg.get("project", "")
        if "/" not in project or project.startswith("yourname/"):
            errors.append("publish.yaml の itch.project を「ユーザー名/プロジェクト名」で設定してください")
        if live and not shutil.which("butler"):
            errors.append("butler コマンドが見つかりません")
        return errors

    def create(self, ctx: Context) -> Result:
        project = ctx.cfg.get("project", "")
        channel = f"{ctx.cfg.get('channel_prefix', 'assets')}-{ctx.listing.id}"
        target = f"{project}:{channel}"
        ctx.transport.run(
            ["butler", "push", str(ctx.package), target, "--userversion", ctx.listing.version],
            env=dict(os.environ),
        )
        return Result(status="uploaded", remote_id=target,
                      url=f"https://{project.split('/')[0]}.itch.io/{project.split('/')[-1]}",
                      note="itch.io のページで価格・説明が最新か確認してください")

    def update(self, ctx: Context, previous: dict) -> Result:
        return self.create(ctx)   # butler は同じチャンネルに上げ直すと差分だけ送る
