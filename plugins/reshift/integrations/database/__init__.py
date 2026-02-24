"""PostgreSQL database integration for Paradigm's internal DB."""

from .client import Database, get_db

__all__ = ["Database", "get_db"]
