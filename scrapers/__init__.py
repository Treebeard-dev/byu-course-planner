"""Catalog scraper adapters, one per vendor platform."""

from .base import Course, CatalogAdapter
from .coursedog import CoursedogAdapter

__all__ = ["Course", "CatalogAdapter", "CoursedogAdapter"]
