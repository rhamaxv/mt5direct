import ast
import pathlib

from mt5direct import MT5Client


def _public_methods(path):
    tree = ast.parse(pathlib.Path(path).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    return {n.name for n in cls.body if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')}


def test_facade_exposes_every_service_method():
    root = pathlib.Path(__file__).resolve().parents[1] / "src" / "mt5direct" / "services"
    expected = set()
    for f in ("auth.py", "account.py", "symbols.py", "market_data.py", "trading.py", "positions.py"):
        expected |= _public_methods(root / f)
    expected -= {"request", "dispatch", "parse_ticks", "stop", "relogin", "off_tick", "listener_running"}   # internal or service-only helpers
    missing = expected - set(dir(MT5Client))
    assert not missing, missing
