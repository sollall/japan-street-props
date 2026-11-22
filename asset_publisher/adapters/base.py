"""販売先アダプタの共通の型。

新しい販売先を足すときは Adapter を継承して check / create / update を書き、
adapters/__init__.py の ADAPTERS に登録するだけでよい。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..listing import Listing
from ..transport import Transport


@dataclass
class Context:
    listing: Listing
    cfg: dict                 # publish.yaml の targets.<販売先>
    package: Path             # この販売先向けに梱包した zip
    out_dir: Path             # この販売先・このアセット用の出力ディレクトリ
    transport: Transport

    @property
    def dry_run(self) -> bool:
        return self.transport.dry_run


@dataclass
class Result:
    status: str               # draft / updated / kit_ready
    remote_id: str | None = None
    url: str | None = None
    note: str = ""


class Adapter:
    name: str = ""
    kind: str = "api"                     # "api"（自動で下書き作成）/ "kit"（手作業用キット）
    default_formats: list[str] = []
    lang: str = "en"
    env_vars: list[str] = []              # 必要な環境変数

    def formats(self, cfg: dict) -> list[str]:
        return cfg.get("formats") or self.default_formats

    def check(self, listing: Listing, cfg: dict, live: bool) -> list[str]:
        """この販売先に出すための追加チェック。問題点のリストを返す。"""
        errors = []
        if live:
            for var in self.env_vars:
                if not os.environ.get(var):
                    errors.append(f"環境変数 {var} が設定されていません")
        if not listing.files_for(self.formats(cfg)):
            errors.append(f"受け付ける形式（{', '.join(self.formats(cfg))}）のファイルがありません")
        return errors

    def create(self, ctx: Context) -> Result:
        raise NotImplementedError

    def update(self, ctx: Context, previous: dict) -> Result:
        """既に出品済みのものを新しいバージョンに更新する。既定では新規作成と同じ。"""
        return self.create(ctx)


def env(name: str, dry_run: bool) -> str:
    """環境変数を読む。リハーサル実行のときは未設定でもダミー値を返す。"""
    value = os.environ.get(name, "")
    if not value and dry_run:
        return f"<{name}>"
    return value
