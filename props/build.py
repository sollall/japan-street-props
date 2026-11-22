"""小物モデルを生成して assets/<名前>/ に書き出す。

  python -m props.build                    全部作る
  python -m props.build guardrail          指定したものだけ
  python -m props.build --no-render        プレビュー画像を描かない（速い）

出力: assets/<名前>/files/<名前>.{blend,fbx,glb} と images/{front,side,top,perspective}.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .common import bounds, export_all, render_previews, reset, triangle_count
from .models import MODELS

ROOT = Path(__file__).resolve().parent.parent


def build(name: str, render: bool = True) -> None:
    reset()
    objects = MODELS[name]()
    lo, hi = bounds(objects)
    d = hi - lo
    out = ROOT / "assets" / name
    export_all(objects, out / "files", name)
    if render:
        render_previews(objects, out / "images")
    print(f"[{name}] 三角形 {triangle_count(objects):,} / 大きさ {d.x:.2f} x {d.y:.2f} x {d.z:.2f} m → {out}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="路上小物のモデルを生成する")
    p.add_argument("names", nargs="*", help=f"作るもの（省略時は全部）: {', '.join(MODELS)}")
    p.add_argument("--no-render", action="store_true", help="プレビュー画像を描かない")
    args = p.parse_args(argv)
    unknown = [n for n in args.names if n not in MODELS]
    if unknown:
        print(f"不明な名前: {', '.join(unknown)}", file=sys.stderr)
        return 2
    for name in args.names or MODELS:
        build(name, render=not args.no_render)
    return 0


if __name__ == "__main__":
    sys.exit(main())
