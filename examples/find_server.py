#!/usr/bin/env python3
"""Search the MetaQuotes server directory and resolve a name to its web terminal host."""

import sys

from mt5direct import ServerNotFound, list_servers, resolve_server


def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "Exness"
    names = list_servers(query)
    print(f"{len(names)} servers match '{query}':")
    for n in names[:20]:
        print("  ", n)

    for name in names[:3]:
        try:
            ep = resolve_server(name)
            print(f"{name:24} -> {ep.host}  ({ep.broker}, build {ep.build})")
        except ServerNotFound as e:
            print(f"{name:24} -> not found: {e}")


if __name__ == "__main__":
    main()
