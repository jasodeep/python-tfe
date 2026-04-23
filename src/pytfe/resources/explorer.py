# Copyright IBM Corp. 2025, 2026
# SPDX-License-Identifier: MPL-2.0

"""Explorer API resource."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

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


def _query_params(options: ExplorerQueryOptions) -> dict[str, Any]:
    params = options.model_dump(by_alias=True, exclude_none=True, exclude={"filters"})
    if options.filters:
        for flt in options.filters:
            params[
                f"filter[{flt.index}][{flt.field}][{flt.operator}][{flt.value_index}]"
            ] = flt.value
    return params


def _parse_row(item: dict[str, Any]) -> ExplorerRow:
    return ExplorerRow.model_validate(item)


def _parse_saved_view(item: dict[str, Any]) -> ExplorerSavedView:
    attrs = item.get("attributes", {})
    return ExplorerSavedView.model_validate(
        {
            "id": item.get("id"),
            "name": attrs.get("name"),
            "created-at": attrs.get("created-at"),
            "query": attrs.get("query", {}),
            "query-type": attrs.get("query-type"),
        }
    )


class Explorer(_Service):
    """Explorer API for Terraform Enterprise."""

    def query(
        self, organization: str, options: ExplorerQueryOptions
    ) -> Iterator[ExplorerRow]:
        if not valid_string_id(organization):
            raise InvalidOrgError()
        path = f"/api/v2/organizations/{organization}/explorer"
        for item in self._list(path, params=_query_params(options)):
            yield _parse_row(item)

    def export_csv(self, organization: str, options: ExplorerQueryOptions) -> str:
        if not valid_string_id(organization):
            raise InvalidOrgError()
        path = f"/api/v2/organizations/{organization}/explorer/export/csv"
        resp = self.t.request("GET", path, params=_query_params(options))
        return resp.text

    def list_saved_views(self, organization: str) -> Iterator[ExplorerSavedView]:
        if not valid_string_id(organization):
            raise InvalidOrgError()
        path = f"/api/v2/organizations/{organization}/explorer/views"
        for item in self._list(path):
            yield _parse_saved_view(item)

    def create_saved_view(
        self, organization: str, options: ExplorerSavedViewCreateOptions
    ) -> ExplorerSavedView:
        if not valid_string_id(organization):
            raise InvalidOrgError()
        body = {
            "data": {
                "type": "explorer-saved-queries",
                "attributes": options.model_dump(by_alias=True, exclude_none=True),
            }
        }
        path = f"/api/v2/organizations/{organization}/explorer/views"
        resp = self.t.request("POST", path, json_body=body)
        return _parse_saved_view(resp.json()["data"])

    def read_saved_view(self, organization: str, view_id: str) -> ExplorerSavedView:
        if not valid_string_id(organization):
            raise InvalidOrgError()
        if not valid_string_id(view_id):
            raise InvalidExplorerSavedViewIDError()
        path = f"/api/v2/organizations/{organization}/explorer/views/{view_id}"
        resp = self.t.request("GET", path)
        return _parse_saved_view(resp.json()["data"])

    def update_saved_view(
        self,
        organization: str,
        view_id: str,
        options: ExplorerSavedViewUpdateOptions,
    ) -> ExplorerSavedView:
        if not valid_string_id(organization):
            raise InvalidOrgError()
        if not valid_string_id(view_id):
            raise InvalidExplorerSavedViewIDError()
        body = {
            "data": {
                "type": "explorer-saved-queries",
                "id": view_id,
                "attributes": options.model_dump(by_alias=True, exclude_none=True),
            }
        }
        path = f"/api/v2/organizations/{organization}/explorer/views/{view_id}"
        resp = self.t.request("PATCH", path, json_body=body)
        return _parse_saved_view(resp.json()["data"])

    def delete_saved_view(self, organization: str, view_id: str) -> ExplorerSavedView:
        if not valid_string_id(organization):
            raise InvalidOrgError()
        if not valid_string_id(view_id):
            raise InvalidExplorerSavedViewIDError()
        path = f"/api/v2/organizations/{organization}/explorer/views/{view_id}"
        resp = self.t.request("DELETE", path)
        return _parse_saved_view(resp.json()["data"])

    def saved_view_results(
        self, organization: str, view_id: str
    ) -> Iterator[ExplorerRow]:
        if not valid_string_id(organization):
            raise InvalidOrgError()
        if not valid_string_id(view_id):
            raise InvalidExplorerSavedViewIDError()
        path = f"/api/v2/organizations/{organization}/explorer/views/{view_id}/results"
        for item in self._list(path):
            yield _parse_row(item)

    def saved_view_results_csv(self, organization: str, view_id: str) -> str:
        if not valid_string_id(organization):
            raise InvalidOrgError()
        if not valid_string_id(view_id):
            raise InvalidExplorerSavedViewIDError()
        path = f"/api/v2/organizations/{organization}/explorer/views/{view_id}/csv"
        resp = self.t.request("GET", path)
        return resp.text
