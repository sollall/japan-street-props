"""販売先ごとの梱包（その販売先が受け付ける形式のファイルだけを zip にまとめる）。"""

from __future__ import annotations

import zipfile
from pathlib import Path

from .listing import Listing

# zip のタイムスタンプを固定して、中身が同じなら同じ zip になるようにする
_FIXED_TIME = (2020, 1, 1, 0, 0, 0)


def build_package(listing: Listing, formats: list[str] | None, out_path: Path) -> Path:
    files = listing.files_for(formats)
    if not files:
        wanted = ", ".join(formats or [])
        raise ValueError(f"この販売先が受け付ける形式（{wanted}）のファイルが listing にありません")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(files, key=lambda x: x.path.name):
            info = zipfile.ZipInfo(f"{listing.id}/{f.path.name}", date_time=_FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, f.path.read_bytes())
        readme = (
            f"{listing.title.get('en', '')}\n"
            f"version: {listing.version}\n"
            f"license: {listing.license}\n"
            f"formats: {', '.join(sorted({f.format for f in files}))}\n"
        )
        info = zipfile.ZipInfo(f"{listing.id}/README.txt", date_time=_FIXED_TIME)
        zf.writestr(info, readme)
    return out_path
