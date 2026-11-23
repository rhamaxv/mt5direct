#!/usr/bin/env python3
"""The MT5 app flow in code: search a company, list its servers, resolve one, connect.

    python examples/find_server.py finex
"""

import sys

from mt5direct import MT5Client, ServerNotFound, list_servers, resolve_server


def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "Exness"

    names = list_servers(query)
    print(f"{len(names)} servers match '{query}':")
    for n in names[:20]:
        print("  ", n)
    if not names:
        return

    for name in names[:3]:
        try:
            ep = resolve_server(name)
            print(f"{name:28} -> {ep.address}  ({ep.broker}, build {ep.build})")
        except ServerNotFound as e:
            print(f"{name:28} -> {e}")

    with MT5Client.from_server(names[0]) as client:
        print(f"connected to {client.address} (server id {client.server_id}); call client.login(...) next")


if __name__ == "__main__":
    main()
