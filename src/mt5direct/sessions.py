"""Persist a logged-in session so later runs skip the password.

A saved session holds the server name or host, the login id, the 160-byte login
token and its ``um`` companion, the per-client ``device_hash`` and the server's
``wt_dtoken`` cookie. The server accepts the token only when all three travel
together, which is why they are stored as one unit. The password is never written.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .discovery import cache_dir


@dataclass(frozen=True, slots=True)
class SavedSession:
    login: int
    token: bytes
    um: int
    device_hash: bytes
    cookie: Optional[str]
    server: Optional[str] = None
    host: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "login": self.login, "token": self.token.hex(), "um": self.um,
            "device_hash": self.device_hash.hex(), "cookie": self.cookie,
            "server": self.server, "host": self.host,
        }

    @classmethod
    def from_json(cls, d: dict) -> "SavedSession":
        return cls(login=int(d["login"]), token=bytes.fromhex(d["token"]), um=int(d.get("um", 0)),
                   device_hash=bytes.fromhex(d["device_hash"]), cookie=d.get("cookie"),
                   server=d.get("server"), host=d.get("host"))


def default_session_path(login: int, server: Optional[str], host: Optional[str]) -> Path:
    name = f"{login}@{server or host or 'default'}".replace("/", "_").replace(":", "_")
    return cache_dir() / "sessions" / f"{name}.json"


def write_session(session: SavedSession, path: Optional[Path] = None) -> Path:
    path = Path(path) if path else default_session_path(session.login, session.server, session.host)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(session.to_json(), indent=2))
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    return path


def read_session(path: Path) -> SavedSession:
    return SavedSession.from_json(json.loads(Path(path).read_text()))


def delete_session(path: Path) -> None:
    try:
        Path(path).unlink()
    except FileNotFoundError:
        pass
