"""HTTP 送信と外部コマンド実行。

リハーサル実行（dry_run）のときは何も送らず、送る予定の内容を記録するだけにする。
テストでもこの記録を使って、各販売先へ送る内容を確認する。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import requests


class SendError(RuntimeError):
    pass


@dataclass
class Call:
    kind: str                 # "http" / "cmd"
    method: str = ""
    url: str = ""
    data: dict | None = None
    json: dict | None = None
    files: dict[str, str] | None = None   # フィールド名 → ファイル名
    cmd: list[str] | None = None


@dataclass
class Transport:
    dry_run: bool = True
    timeout: int = 600
    calls: list[Call] = field(default_factory=list)
    session: requests.Session | None = None

    def http(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        data: dict | list | None = None,
        json: dict | None = None,
        files: dict[str, Path] | None = None,
    ) -> dict:
        self.calls.append(
            Call(
                kind="http",
                method=method,
                url=url,
                data=dict(data) if isinstance(data, dict) else ({"_list": data} if data else None),
                json=json,
                files={k: Path(v).name for k, v in (files or {}).items()} or None,
            )
        )
        if self.dry_run:
            return {"_dry_run": True}

        session = self.session or requests.Session()
        opened = {k: open(v, "rb") for k, v in (files or {}).items()}
        try:
            r = session.request(
                method, url, headers=headers, data=data, json=json,
                files=opened or None, timeout=self.timeout,
            )
        finally:
            for fh in opened.values():
                fh.close()
        if r.status_code >= 400:
            raise SendError(f"{method} {url} → {r.status_code}: {r.text[:500]}")
        out: dict = {}
        if r.content:
            try:
                out = r.json()
            except ValueError:
                out = {"_text": r.text}
        if "Location" in r.headers:
            out.setdefault("_location", r.headers["Location"])
        return out

    def run(self, cmd: list[str], env: dict | None = None) -> str:
        self.calls.append(Call(kind="cmd", cmd=list(cmd)))
        if self.dry_run:
            return ""
        p = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if p.returncode != 0:
            raise SendError(f"{' '.join(cmd)} が失敗: {p.stderr[-500:]}")
        return p.stdout
