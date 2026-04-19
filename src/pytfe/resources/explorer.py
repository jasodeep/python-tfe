# Copyright IBM Corp. 2025, 2026
# SPDX-License-Identifier: MPL-2.0

"""Explorer client: organization-level workspace visibility (API v2).

Base path: ``/api/v2/organizations/{organization}/explorer`` and
``.../explorer/views``. Authorization matches the Explorer API (org owners, teams
with broad read, org-scoped tokens where applicable).

List-like iterators (:meth:`query`, :meth:`saved_view_results`, :meth:`list_saved_views`)
use the same pagination contract as :meth:`pytfe.resources._base._Service._list`:
advance ``page[number]`` until a page returns fewer than ``page[size]`` rows.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

from ..errors import InvalidExplorerSavedViewIDError, InvalidOrgError
from ..models.explorer import (
    ExplorerQueryOptions,
    ExplorerRow,
    ExplorerSavedView,
    ExplorerSavedViewCreateOptions,
    ExplorerSavedViewUpdateOptions,
)
from ..utils import valid_string_id
from ._base import _Service


def _params_from_query_options(options: ExplorerQueryOptions) -> dict[str, str]:
    """Merge static Explorer query params with dynamic ``filter[...]`` keys.

    ``ExplorerQueryOptions.filters`` cannot round-trip through a single
    :meth:`~pytfe.models.explorer.ExplorerQueryOptions.model_dump` because each filter
    expands to a uniquely keyed query parameter.
    """
    raw = options.model_dump(
        by_alias=True,
        exclude_none=True,
        exclude={"filters"},
        mode="json",
    )
    out: dict[str, str] = {}
    for key, val in raw.items():
        if val is None:
            continue
        out[str(key)] = val if isinstance(val, str) else str(val)
    if options.filters:
        for flt in options.filters:
            pkey = (
                f"filter[{flt.index}][{flt.field}][{flt.operator}][{flt.value_index}]"
            )
            out[pkey] = flt.value
    return out


class Explorer(_Service):
    """Bindings for ``TFEClient.explorer``."""

    @staticmethod
    def _parse_row(item: dict[str, Any]) -> ExplorerRow:
        """Normalize a JSON:API element from ``data[]`` to :class:`~pytfe.models.explorer.ExplorerRow`."""
        return ExplorerRow.model_validate(item)

    @staticmethod
    def _parse_saved_view(data: dict[str, Any]) -> ExplorerSavedView:
        """Build :class:`~pytfe.models.explorer.ExplorerSavedView` from a ``data`` object.

        Attributes arrive kebab-cased; validation uses API-shaped keys so Pydantic
        aliases resolve without manual renaming.
        """
        attr = data.get("attributes") or {}
        payload: dict[str, Any] = {
            "id": data["id"],
            "name": attr["name"],
            "created-at": attr.get("created-at"),
            "query": attr.get("query") or {},
            "query-type": attr.get("query-type") or "",
        }
        return ExplorerSavedView.model_validate(payload)

    def query(
        self, organization: str, options: ExplorerQueryOptions
    ) -> Iterator[ExplorerRow]:
        """Paginated visibility rows for ``GET .../organizations/{organization}/explorer``.

        Args:
            organization: Organization name (unencoded path segment).
            options: ``type`` plus optional ``sort``, ``fields``, URL ``filters``.

        Yields:
            Parsed rows until the API returns a short page.

        Raises:
            InvalidOrgError: ``organization`` fails :func:`~pytfe.utils.valid_string_id`.
        """
        if not valid_string_id(organization):
            raise InvalidOrgError()

        base = _params_from_query_options(options)
        path = f"/api/v2/organizations/{quote(organization)}/explorer"
        page = 1
        while True:
            params = dict(base)
            params["page[number]"] = str(page)
            params.setdefault("page[size]", "100")
            r = self.t.request("GET", path, params=params)
            body = r.json()
            if body is None:
                break
            data = body.get("data") or []
            for item in data:
                yield self._parse_row(item)
            page_size = int(params["page[size]"])
            if len(data) < page_size:
                break
            page += 1

    def export_csv(self, organization: str, options: ExplorerQueryOptions) -> str:
        """Unpaged CSV for the same selection as :meth:`query` (``GET .../explorer/export/csv``).

        Response is raw text/csv, not JSON.

        Raises:
            InvalidOrgError: Invalid ``organization``.
        """
        if not valid_string_id(organization):
            raise InvalidOrgError()

        params = _params_from_query_options(options)
        path = f"/api/v2/organizations/{quote(organization)}/explorer/export/csv"
        r = self.t.request("GET", path, params=params)
        return r.text

    def list_saved_views(self, organization: str) -> Iterator[ExplorerSavedView]:
        """Saved views under ``GET .../explorer/views`` (paginated via :meth:`_list`)."""

        if not valid_string_id(organization):
            raise InvalidOrgError()

        path = f"/api/v2/organizations/{quote(organization)}/explorer/views"
        for item in self._list(path):
            yield self._parse_saved_view(item)

    def create_saved_view(
        self, organization: str, options: ExplorerSavedViewCreateOptions
    ) -> ExplorerSavedView:
        """``POST .../explorer/views`` with ``type: explorer-saved-queries``."""

        if not valid_string_id(organization):
            raise InvalidOrgError()

        attrs = options.model_dump(by_alias=True, exclude_none=True, mode="json")
        body: dict[str, Any] = {
            "data": {
                "type": "explorer-saved-queries",
                "attributes": attrs,
            }
        }
        path = f"/api/v2/organizations/{quote(organization)}/explorer/views"
        r = self.t.request("POST", path, json_body=body)
        data = r.json()["data"]
        return self._parse_saved_view(data)

    def read_saved_view(self, organization: str, view_id: str) -> ExplorerSavedView:
        """``GET .../explorer/views/{view_id}``.

        Raises:
            InvalidOrgError: Invalid ``organization``.
            InvalidExplorerSavedViewIDError: Invalid ``view_id``.
        """

        if not valid_string_id(organization):
            raise InvalidOrgError()
        if not valid_string_id(view_id):
            raise InvalidExplorerSavedViewIDError()

        path = f"/api/v2/organizations/{quote(organization)}/explorer/views/{quote(view_id)}"
        r = self.t.request("GET", path)
        data = r.json()["data"]
        return self._parse_saved_view(data)

    def update_saved_view(
        self,
        organization: str,
        view_id: str,
        options: ExplorerSavedViewUpdateOptions,
    ) -> ExplorerSavedView:
        """``PATCH .../explorer/views/{view_id}``; includes ``data.id`` for JSON:API.

        Raises:
            InvalidOrgError: Invalid ``organization``.
            InvalidExplorerSavedViewIDError: Invalid ``view_id``.
        """

        if not valid_string_id(organization):
            raise InvalidOrgError()
        if not valid_string_id(view_id):
            raise InvalidExplorerSavedViewIDError()

        attrs = options.model_dump(by_alias=True, exclude_none=True, mode="json")
        body: dict[str, Any] = {
            "data": {
                "type": "explorer-saved-queries",
                "id": view_id,
                "attributes": attrs,
            }
        }
        path = f"/api/v2/organizations/{quote(organization)}/explorer/views/{quote(view_id)}"
        r = self.t.request("PATCH", path, json_body=body)
        data = r.json()["data"]
        return self._parse_saved_view(data)

    def delete_saved_view(self, organization: str, view_id: str) -> ExplorerSavedView:
        """``DELETE .../explorer/views/{view_id}``; response still carries ``data``.

        Raises:
            InvalidOrgError: Invalid ``organization``.
            InvalidExplorerSavedViewIDError: Invalid ``view_id``.
        """

        if not valid_string_id(organization):
            raise InvalidOrgError()
        if not valid_string_id(view_id):
            raise InvalidExplorerSavedViewIDError()

        path = f"/api/v2/organizations/{quote(organization)}/explorer/views/{quote(view_id)}"
        r = self.t.request("DELETE", path)
        data = r.json()["data"]
        return self._parse_saved_view(data)

    def saved_view_results(
        self, organization: str, view_id: str
    ) -> Iterator[ExplorerRow]:
        """Re-run a saved query: ``GET .../explorer/views/{view_id}/results``.

        Raises:
            InvalidOrgError: Invalid ``organization``.
            InvalidExplorerSavedViewIDError: Invalid ``view_id``.
        """

        if not valid_string_id(organization):
            raise InvalidOrgError()
        if not valid_string_id(view_id):
            raise InvalidExplorerSavedViewIDError()

        path = f"/api/v2/organizations/{quote(organization)}/explorer/views/{quote(view_id)}/results"
        page = 1
        while True:
            params: dict[str, str] = {
                "page[number]": str(page),
                "page[size]": "100",
            }
            r = self.t.request("GET", path, params=params)
            body = r.json()
            if body is None:
                break
            data = body.get("data") or []
            for item in data:
                yield self._parse_row(item)
            page_size = int(params["page[size]"])
            if len(data) < page_size:
                break
            page += 1

    def saved_view_results_csv(self, organization: str, view_id: str) -> str:
        """``GET .../explorer/views/{view_id}/csv``; same logical query as :meth:`saved_view_results`.

        Raises:
            InvalidOrgError: Invalid ``organization``.
            InvalidExplorerSavedViewIDError: Invalid ``view_id``.
        """

        if not valid_string_id(organization):
            raise InvalidOrgError()
        if not valid_string_id(view_id):
            raise InvalidExplorerSavedViewIDError()

        path = f"/api/v2/organizations/{quote(organization)}/explorer/views/{quote(view_id)}/csv"
        r = self.t.request("GET", path)
        return r.text
