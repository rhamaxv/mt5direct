"""Resolve MT5 trade server names to web terminal hosts.

Every broker runs its own MT5 Web Terminal host (Exness: ``mt5trial6.exwebterm.com``,
MetaQuotes: ``web.metatrader.app``). Each host serves exactly one trade server and
announces it in ``window.__terminal_params`` on its ``/terminal`` page. Resolution
therefore has two steps: guess candidate hosts from the server name, then verify a
candidate by reading that announcement.
"""

import json
import re
import ssl
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from .constants.network import WS_PATH
from .exceptions import ServerNotFound

SERVERS_API = "https://metatraderweb.app/trade/servers?version=5&all=1"

BROKER_DOMAINS = {
    "Exness": "exwebterm.com",
}
"""Broker prefix (text before the first ``-`` in a server name) to web terminal domain."""

KNOWN_HOSTS = {
    "MetaQuotes-Demo": "web.metatrader.app",
}
"""Server names whose host does not follow a broker-wide pattern."""

_USER_AGENT = "Mozilla/5.0 (compatible; mt5direct)"
_PARAMS_RE = re.compile(r"__terminal_params\s*=\s*(\{.*?\})\s*;?\s*</script>", re.S)

Fetcher = Callable[[str, float], str]


@dataclass(frozen=True, slots=True)
class Endpoint:
    """A verified web terminal host for one trade server."""

    host: str
    server: str
    broker: str
    build: int
    path: str = WS_PATH


def _fetch(url: str, timeout: float) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", "replace")


def list_servers(search: Optional[str] = None, timeout: float = 15, fetch: Fetcher = _fetch) -> list[str]:
    """All MT5 trade server names known to MetaQuotes, optionally filtered by substring."""
    data = json.loads(fetch(SERVERS_API, timeout))
    servers = data.get("mt5", [])
    if search:
        needle = search.lower()
        servers = [s for s in servers if needle in s.lower()]
    return servers


def split_server_name(name: str) -> tuple[str, str]:
    """``'Exness-MT5Trial6'`` -> ``('Exness', 'MT5Trial6')``. Code is empty if there is no dash."""
    broker, _, code = name.partition("-")
    return broker, code


def candidate_hosts(name: str) -> list[str]:
    """Hosts worth checking for ``name``, most likely first. Unverified guesses."""
    hosts = []
    if name in KNOWN_HOSTS:
        hosts.append(KNOWN_HOSTS[name])
    broker, code = split_server_name(name)
    if broker and code:
        domain = BROKER_DOMAINS.get(broker)
        if domain:
            hosts.append(f"{code.lower()}.{domain}")
        hosts.append(f"{code.lower()}.{broker.lower()}webterm.com")
    return list(dict.fromkeys(hosts))


def parse_terminal_params(html: str) -> Optional[dict]:
    """Extract ``window.__terminal_params`` from a web terminal page, or ``None``."""
    m = _PARAMS_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def inspect_host(host: str, timeout: float = 10, fetch: Fetcher = _fetch) -> list[Endpoint]:
    """Servers announced by the web terminal at ``host``. Empty if unreachable or not a terminal."""
    try:
        html = fetch(f"https://{host}{WS_PATH}", timeout)
    except Exception:
        return []
    params = parse_terminal_params(html)
    if not params:
        return []
    broker = (params.get("broker") or {}).get("name", "")
    build = int(params.get("build") or 0)
    return [
        Endpoint(host=host, server=s["server"], broker=broker, build=build)
        for s in params.get("servers", []) if s.get("server")
    ]


def resolve_server(name: str, timeout: float = 10, fetch: Fetcher = _fetch) -> Endpoint:
    """Find and verify the web terminal host serving trade server ``name``.

    Raises ``ServerNotFound`` when no candidate host announces that server.
    """
    candidates = candidate_hosts(name)
    tried = []
    for host in candidates:
        tried.append(host)
        for ep in inspect_host(host, timeout, fetch):
            if ep.server.lower() == name.lower():
                return ep
    raise ServerNotFound(
        f"No web terminal host found for '{name}' (tried: {', '.join(tried) or 'nothing'}). "
        f"Pass host= explicitly, or add the broker's domain to mt5direct.discovery.BROKER_DOMAINS."
    )
