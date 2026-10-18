"""Paginación: número de página validado y paginación en memoria para listas del API."""
import re
from math import ceil

PAGE_RE = re.compile(r"^[0-9]{1,4}\Z")


def get_page(args):
    """Página validada (1..9999); cualquier otro valor (-1, abc, 10^20) se trata como 1."""
    raw = args.get("page", "1")
    if not isinstance(raw, str) or not PAGE_RE.match(raw):
        return 1
    return max(int(raw), 1)


class ListPagination:
    """Misma interfaz que la paginación de SQLAlchemy, para listas que vienen del API."""

    def __init__(self, items, page, per_page):
        self.total = len(items)
        self.per_page = per_page
        self.pages = ceil(self.total / per_page) if self.total else 0
        self.page = min(max(page, 1), max(self.pages, 1))
        start = (self.page - 1) * per_page
        self.items = items[start:start + per_page]
        self.has_prev = self.page > 1
        self.has_next = self.page < self.pages
        self.prev_num = self.page - 1 if self.has_prev else None
        self.next_num = self.page + 1 if self.has_next else None
