# Contributing

## Setup

```bash
git clone https://github.com/rhamaxv/mt5direct
cd mt5direct
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## Commit messages

One line, `type: sentence`, no body:

```
fix: handle empty tick payload in parse_ticks
feat: add deal commission to Deal model
docs: document server selection
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`.

## Adding a field to an existing record

1. Add the offset to `protocol/layouts.py` if it is a new record size or
   base offset; otherwise read it inline in the parser.
2. Add the field to the dataclass in `models/`.
3. Decode it in the matching `parsers/` module.
4. Extend the test in `tests/parsers/` with the new bytes and assertion.
5. Update the table in `docs/protocol.md` and `docs/api.md`.

## Adding a command

1. Add `CMD_<NAME>` to `constants/commands.py` and the table in `docs/protocol.md`.
2. Add a parser (pure function, bytes in, model out) with a test.
3. Add a method on the owning service in `services/`; use `self.request(cmd, payload, timeout)`.
4. Expose it on `MT5Client` as a one-line delegation and list it in `docs/api.md`.

## Rules

- Parsers never touch the network; services never parse bytes inline.
- Imports only point downward (see `docs/architecture.md`).
- No credentials in code or tests. Examples read `MT5_LOGIN` / `MT5_PASSWORD`.
- Keep the public method names stable; add, do not rename.

## Releasing

Bump `version` in `pyproject.toml`, commit, then `git tag vX.Y.Z && git push --tags`.
The publish workflow does the rest.
