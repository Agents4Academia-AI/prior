"""Primary-source adapters. Each returns `Paper` objects with citation edges
where available, so the atlas is grounded in real bibliographic data rather
than web-search snippets."""

from .openalex import search as openalex_search, fetch as openalex_fetch
from .arxiv import search as arxiv_search

__all__ = ["openalex_search", "openalex_fetch", "arxiv_search"]
