"""出品処理の本体。各アセット × オンになっている販売先 の組み合わせを順に処理する。

1つの販売先で失敗しても、他の販売先の処理は続ける。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .adapters import ADAPTERS, Context
from .config import Config
from .listing import Listing, validate_listing
from .package import build_package
from .state import State
from .transport import Call, Transport


@dataclass
class Outcome:
    asset: str
    target: str
    action: str               # create / update / skip / error
    status: str = ""
    url: str | None = None
    note: str = ""
    calls: list[Call] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.action != "error"


def publish(
    config: Config,
    listings: list[Listing],
    targets: list[str],
    *,
    live: bool = False,
    force: bool = False,
) -> list[Outcome]:
    state = State(config.state_file)
    outcomes: list[Outcome] = []

    for listing in listings:
        common_errors = validate_listing(listing)
        for name in targets:
            adapter = ADAPTERS[name]
            cfg = config.target(name)

            errors = common_errors + adapter.check(listing, cfg, live)
            if errors:
                outcomes.append(Outcome(listing.id, name, "error", note=" / ".join(errors)))
                continue

            previous = state.get(listing.id, name)
            if previous and previous.get("version") == listing.version and not force:
                outcomes.append(Outcome(listing.id, name, "skip", previous.get("status", ""),
                                        previous.get("url"), "同じバージョンを出品済み（--force で再実行）"))
                continue

            transport = Transport(dry_run=not live)
            out_dir = config.out_dir / listing.id / name
            try:
                package = build_package(listing, adapter.formats(cfg),
                                        config.out_dir / listing.id / "_packages" / f"{name}.zip")
                ctx = Context(listing=listing, cfg=cfg, package=package, out_dir=out_dir, transport=transport)
                is_update = bool(previous) and not force
                result = adapter.update(ctx, previous) if is_update else adapter.create(ctx)
            except Exception as e:  # noqa: BLE001  販売先ごとの失敗を他に波及させない
                outcomes.append(Outcome(listing.id, name, "error", note=str(e), calls=transport.calls))
                continue

            outcomes.append(Outcome(listing.id, name, "update" if is_update else "create",
                                    result.status, result.url, result.note, transport.calls))
            if live:
                state.put(listing.id, name, version=listing.version, status=result.status,
                          remote_id=result.remote_id, url=result.url)
                state.save()   # 途中で止まっても、そこまでの記録は残す

    return outcomes


def record(config: Config, listing: Listing, target: str, url: str | None, remote_id: str | None) -> None:
    """手作業で出品した結果（URLなど）を出品履歴に書き込む。"""
    state = State(config.state_file)
    prev = state.get(listing.id, target) or {}
    state.put(listing.id, target, version=listing.version, status="listed",
              remote_id=remote_id or prev.get("remote_id"), url=url or prev.get("url"))
    state.save()
