"""Package data (model parameters and tables shipped with pencilmark)."""
from __future__ import annotations

import json
from importlib import resources


def path(name):
    """a file in pencilmark/data as an importlib Traversable."""
    return resources.files(__package__).joinpath("data", name)


def exists(name):
    return path(name).is_file()


def read_text(name):
    return path(name).read_text(encoding="utf-8")


def load_json(name):
    return json.loads(read_text(name))


def _int_keys(x):
    """JSON stores dict keys as strings; the engine's price tables are keyed by technique id (int)."""
    if isinstance(x, dict):
        if x and all(isinstance(k, str) and k.lstrip("-").isdigit() for k in x):
            return {int(k): _int_keys(v) for k, v in x.items()}
        return {k: _int_keys(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_int_keys(v) for v in x]
    return x


def load_params(name="params.json"):
    """raw engine parameters (before scoring.complete_params)."""
    return _int_keys(load_json(name))
