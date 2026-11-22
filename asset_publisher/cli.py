"""コマンドライン。

  asset-publisher targets                         販売先のオン・オフ一覧
  asset-publisher publish <listing.yaml>...       リハーサル実行（送信しない）
  asset-publisher publish <listing.yaml>... --live    実際に送信する
      --only sketchfab,fab   この販売先だけ（設定ファイルの enabled を無視）
      --enable etsy          今回だけオンにする
      --disable booth        今回だけオフにする
      --force                出品済みでも新規作成し直す
  asset-publisher record <listing.yaml> <販売先> --url <URL>   手作業で出品した結果を記録
"""

from __future__ import annotations

import argparse
import sys

from .adapters import ADAPTERS
from .config import load_config, resolve_enabled
from .listing import load_listing
from .runner import publish, record

KNOWN = list(ADAPTERS)
MARK = {"create": "新規", "update": "更新", "skip": "スキップ", "error": "エラー"}


def _targets(args, config) -> list[str]:
    return resolve_enabled(config, KNOWN, only=args.only, enable=args.enable, disable=args.disable)


def cmd_targets(args) -> int:
    config = load_config(args.config)
    selected = _targets(args, config)
    for name in KNOWN:
        a = ADAPTERS[name]
        on = "ON " if name in selected else "off"
        kind = "API で下書き作成" if a.kind == "api" else "手作業用キット"
        print(f"  [{on}] {name:<10} {kind:<16} 形式: {', '.join(a.formats(config.target(name)))}")
    return 0


def cmd_publish(args) -> int:
    config = load_config(args.config)
    targets = _targets(args, config)
    if not targets:
        print("オンになっている販売先がありません（publish.yaml の enabled か --only / --enable を確認）")
        return 1
    listings = [load_listing(p) for p in args.listings]

    mode = "本番送信" if args.live else "リハーサル（送信しません。実際に送るには --live）"
    print(f"モード: {mode}")
    print(f"販売先: {', '.join(targets)}\n")

    outcomes = publish(config, listings, targets, live=args.live, force=args.force)
    for o in outcomes:
        line = f"[{MARK[o.action]}] {o.asset} → {o.target}"
        if o.status:
            line += f"  ({o.status})"
        if o.url:
            line += f"  {o.url}"
        print(line)
        if o.note:
            print(f"    {o.note}")
        if not args.live or args.verbose:
            for c in o.calls:
                if c.kind == "http":
                    files = f"  ファイル: {', '.join(c.files.values())}" if c.files else ""
                    print(f"    送信予定: {c.method} {c.url}{files}")
                else:
                    print(f"    実行予定: {' '.join(c.cmd or [])}")

    failed = [o for o in outcomes if not o.ok]
    print(f"\n完了: {len(outcomes) - len(failed)} 件 / エラー: {len(failed)} 件")
    return 1 if failed else 0


def cmd_record(args) -> int:
    config = load_config(args.config)
    if args.target not in KNOWN:
        print(f"不明な販売先: {args.target}")
        return 1
    listing = load_listing(args.listing)
    record(config, listing, args.target, args.url, args.id)
    print(f"記録しました: {listing.id} v{listing.version} → {args.target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="asset-publisher", description="3Dアセットを複数の販売先へ出品する")
    p.add_argument("--config", default="publish.yaml", help="設定ファイル（既定: publish.yaml）")
    sub = p.add_subparsers(dest="cmd", required=True)

    def toggles(sp):
        sp.add_argument("--only", help="この販売先だけ（カンマ区切り）")
        sp.add_argument("--enable", action="append", help="今回だけオンにする販売先")
        sp.add_argument("--disable", action="append", help="今回だけオフにする販売先")

    sp = sub.add_parser("targets", help="販売先のオン・オフ一覧")
    toggles(sp)
    sp.set_defaults(func=cmd_targets)

    sp = sub.add_parser("publish", help="出品する（既定はリハーサル）")
    sp.add_argument("listings", nargs="+", help="listing.yaml のパス")
    sp.add_argument("--live", action="store_true", help="実際に送信する")
    sp.add_argument("--force", action="store_true", help="出品済みでも新規作成し直す")
    sp.add_argument("-v", "--verbose", action="store_true", help="本番送信でも送信内容を表示")
    toggles(sp)
    sp.set_defaults(func=cmd_publish)

    sp = sub.add_parser("record", help="手作業で出品した結果を記録")
    sp.add_argument("listing")
    sp.add_argument("target")
    sp.add_argument("--url")
    sp.add_argument("--id")
    sp.set_defaults(func=cmd_record)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
