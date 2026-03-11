from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Request


class PaginationService:
    """Service for pagination operations"""

    def __init__(
        self,
        request: Request,
    ):
        self.page: int = int(request.query_params.get("page", 1))
        self.page_size: int = int(request.query_params.get("page_size", 10))
        self.request: Request = request

    def build_paginated_response(self, all_items: list[Any]) -> dict[str, Any]:
        """Build paginated response with prev/next page URLs"""
        # Calculate total pages
        total = len(all_items)
        total_pages = (
            (total + self.page_size - 1) // self.page_size if total > 0 else 0
        )
        offset = (self.page - 1) * self.page_size
        items = all_items[offset : offset + self.page_size]

        # Build base URL - use request.url without query params
        base_url = str(self.request.url).split("?")[0]

        # Calculate previous and next page URLs
        prev_page = None
        next_page = None

        if self.page > 1:
            prev_page = (
                f"{base_url}?page={self.page - 1}&page_size={self.page_size}"
            )

        if self.page < total_pages:
            next_page = (
                f"{base_url}?page={self.page + 1}&page_size={self.page_size}"
            )

        return {
            "items": items,
            "total": total,
            "page": self.page,
            "page_size": self.page_size,
            "prev_page": prev_page,
            "next_page": next_page,
        }


async def get_pagination_service(
    request: Request,
) -> AsyncGenerator[PaginationService]:
    """Dependency for getting PaginationService instance"""
    yield PaginationService(request)
