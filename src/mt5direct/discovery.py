"""Find the MT5 Web Terminal host for a trade server name.

Mirrors the MT5 app flow: search the MetaQuotes directory for a company
(``list_servers``), pick a server name, connect (``MT5Client.from_server``).

Every broker hosts its own web terminal, and each host serves exactly one trade
server, announced in ``window.__terminal_params`` on its ``/terminal`` page.
MetaQuotes publishes server names but never these hosts, so this module keeps a
registry: a JSON file bundled with the package, refreshed from GitHub, extended
by whatever ``resolve_server``/``discover_from_url`` verify on this machine.
"""

import html
import json
import os
import re
import ssl
import time
import urllib.request
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Callable, Optional

from .exceptions import ServerNotFound

SERVERS_API = "https://metatraderweb.app/trade/servers?version=5&all=1"
REGISTRY_URL = "https://raw.githubusercontent.com/rhamaxv/mt5direct/main/src/mt5direct/data/webterminals.json"
REGISTRY_TTL = 24 * 3600
TERMINAL_PATH = "/terminal"
DEFAULT_PORT = 443

_USER_AGENT = "Mozilla/5.0 (compatible; mt5direct)"
_PARAMS_RE = re.compile(r"__terminal_params\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S)
_TERMINAL_URL_RE = re.compile(r"https?://([A-Za-z0-9.-]+)(?::(\d+))?/terminal\b")

Fetcher = Callable[[str, float], str]


@dataclass(frozen=True, slots=True)
class Endpoint:
    """A verified web terminal host for one trade server."""

    host: str
    server: str
    broker: str = ""
    build: int = 0
    port: int = DEFAULT_PORT
    path: str = TERMINAL_PATH

    @property
    def address(self) -> str:
        return self.host if self.port == DEFAULT_PORT else f"{self.host}:{self.port}"


@dataclass
class Registry:
    """Known server-to-host assignments plus per-broker host patterns."""

    servers: dict[str, str] = field(default_factory=dict)
    patterns: dict[str, dict] = field(default_factory=dict)

    def merge(self, other: dict) -> "Registry":
        self.servers.update(other.get("servers") or {})
        self.patterns.update(other.get("patterns") or {})
        return self


def split_address(address: str, default_port: int = DEFAULT_PORT) -> tuple[str, int]:
    """``'host:1951'`` -> ``('host', 1951)``; ``'host'`` -> ``('host', 443)``."""
    host, _, port = address.partition(":")
    return host, int(port) if port else default_port


def split_server_name(name: str) -> tuple[str, str]:
    """``'Exness-MT5Trial6'`` -> ``('Exness', 'MT5Trial6')``. Code is empty if there is no dash."""
    broker, _, code = name.partition("-")
    return broker, code


# -- HTTP ------------------------------------------------------------------

def _fetch(url: str, timeout: float) -> str:
    """HTTPS GET with normal certificate verification."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
        return resp.read().decode("utf-8", "replace")


def list_servers(search: Optional[str] = None, timeout: float = 15, fetch: Fetcher = _fetch) -> list[str]:
    """Trade server names from the MetaQuotes directory, filtered by substring (like the MT5 app's company search)."""
    data = json.loads(fetch(SERVERS_API, timeout))
    servers = data.get("mt5", [])
    if search:
        needle = search.lower()
        servers = [s for s in servers if needle in s.lower()]
    return servers


# -- registry ----------------------------------------------------------------

def cache_dir() -> Path:
    return Path(os.environ.get("MT5DIRECT_CACHE_DIR") or Path.home() / ".cache" / "mt5direct")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _write_json(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True))
    except OSError:
        pass


def bundled_registry() -> dict:
    return json.loads(resources.files("mt5direct.data").joinpath("webterminals.json").read_text())


def remote_registry(timeout: float = 5, fetch: Fetcher = _fetch) -> dict:
    """Registry from GitHub, cached on disk for ``REGISTRY_TTL`` seconds. Empty on failure."""
    path = cache_dir() / "registry.json"
    try:
        if time.time() - path.stat().st_mtime < REGISTRY_TTL:
            return _read_json(path)
    except OSError:
        pass
    try:
        data = json.loads(fetch(REGISTRY_URL, timeout))
    except Exception:
        return _read_json(path)
    _write_json(path, data)
    return data


def learned_registry() -> dict:
    """Endpoints verified earlier on this machine."""
    return _read_json(cache_dir() / "learned.json")


def remember(endpoint: Endpoint) -> None:
    path = cache_dir() / "learned.json"
    data = _read_json(path)
    data.setdefault("servers", {})[endpoint.server] = endpoint.address
    _write_json(path, data)


def load_registry(remote: bool = True, timeout: float = 5, fetch: Fetcher = _fetch) -> Registry:
    """Bundled registry, overlaid with the remote copy and this machine's learned entries."""
    reg = Registry().merge(bundled_registry())
    if remote and not os.environ.get("MT5DIRECT_OFFLINE"):
        reg.merge(remote_registry(timeout, fetch))
    return reg.merge(learned_registry())


# -- resolution ----------------------------------------------------------------

def candidate_addresses(name: str, registry: Registry) -> list[str]:
    """``host[:port]`` strings worth checking for ``name``, most likely first. Unverified."""
    out = []
    exact = registry.servers.get(name)
    if exact:
        out.append(exact)
    broker, code = split_server_name(name)
    if broker and code:
        pat = registry.patterns.get(broker)
        if pat:
            host = pat["host"].format(code=code.lower(), broker=broker.lower())
            port = int(pat.get("port", DEFAULT_PORT))
            out.append(host if port == DEFAULT_PORT else f"{host}:{port}")
        out.append(f"{code.lower()}.{broker.lower()}webterm.com")
        out.append(f"{code.lower()}.webterminal-{broker.lower()}.com")
    return list(dict.fromkeys(out))


def parse_terminal_params(page: str) -> Optional[dict]:
    """Extract ``window.__terminal_params`` from a web terminal page, or ``None``."""
    m = _PARAMS_RE.search(page)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def inspect_host(host: str, port: int = DEFAULT_PORT, timeout: float = 10, fetch: Fetcher = _fetch) -> list[Endpoint]:
    """Servers announced by the web terminal at ``host:port``. Empty if unreachable or not a terminal."""
    try:
        page = fetch(f"https://{host}:{port}{TERMINAL_PATH}", timeout)
    except Exception:
        return []
    params = parse_terminal_params(page)
    if not params:
        return []
    broker = (params.get("broker") or {}).get("name", "")
    build = int(params.get("build") or 0)
    return [
        Endpoint(host=host, port=port, server=s["server"], broker=broker, build=build)
        for s in params.get("servers", []) if s.get("server")
    ]


def resolve_server(name: str, registry: Optional[Registry] = None, timeout: float = 10,
                   fetch: Fetcher = _fetch) -> Endpoint:
    """Find and verify the web terminal host serving trade server ``name``.

    Checks the registry first, then broker patterns and generic host guesses. Every
    candidate is verified against its ``__terminal_params`` announcement; a verified
    guess is remembered for next time. Raises ``ServerNotFound`` otherwise.
    """
    registry = registry or load_registry(fetch=fetch)
    tried = []
    for address in candidate_addresses(name, registry):
        host, port = split_address(address)
        tried.append(address)
        for ep in inspect_host(host, port, timeout, fetch):
            if ep.server.lower() == name.lower():
                if registry.servers.get(name) != ep.address:
                    remember(ep)
                return ep
    raise ServerNotFound(
        f"No web terminal host known for '{name}' (tried: {', '.join(tried) or 'nothing'}). "
        f"Open your broker's web terminal in a browser and run "
        f"discover_from_url('<that page url>') once, or pass host='...' to MT5Client."
    )


def discover_from_url(url: str, timeout: float = 10, fetch: Fetcher = _fetch) -> list[Endpoint]:
    """Scan a broker's web terminal page for ``/terminal`` hosts, verify them, remember them.

    Works with the terminal page itself or with a launcher page that embeds it in an
    iframe or links to it.
    """
    try:
        page = html.unescape(fetch(url, timeout))
    except Exception:
        return []
    addresses = []
    m = _TERMINAL_URL_RE.match(url)
    if m:
        addresses.append((m.group(1), int(m.group(2) or DEFAULT_PORT)))
    for host, port in _TERMINAL_URL_RE.findall(page):
        addresses.append((host, int(port or DEFAULT_PORT)))
    found = []
    for host, port in dict.fromkeys(addresses):
        for ep in inspect_host(host, port, timeout, fetch):
            remember(ep)
            found.append(ep)
    return found
