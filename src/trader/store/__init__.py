"""The only code that writes to data/. Enforces who writes where, and that files only grow."""

from .core import FOLDER_OF, OWNERS, Store, StoreError, Writer

__all__ = ["FOLDER_OF", "OWNERS", "Store", "StoreError", "Writer"]
