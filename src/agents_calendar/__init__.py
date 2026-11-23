"""CalDAV calendar feeler."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("agents-calendar")
except _PackageNotFoundError:  # a source checkout that was never installed
    __version__ = "0.0.0+source"
