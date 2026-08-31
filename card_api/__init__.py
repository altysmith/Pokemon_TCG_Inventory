"""Local, provenance-aware Pokemon TCG card catalog service."""

from __future__ import annotations


def create_app(*args, **kwargs):
    """Load the FastAPI factory lazily so import/update tools stay independent."""
    from .api import create_app as factory

    return factory(*args, **kwargs)


__all__ = ["create_app"]
