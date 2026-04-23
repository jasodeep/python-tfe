# Copyright IBM Corp. 2025, 2026
# SPDX-License-Identifier: MPL-2.0

"""Explorer API resource."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from typing import Any

from ..errors import (
    InvalidExplorerSavedViewIDError,
    InvalidOrgError,
    NotFound,
    ServerError,
)
from ..models.explorer import (
    ExplorerQueryOptions,
    ExplorerRow,
    ExplorerSavedView,
    ExplorerSavedViewCreateOptions,
    ExplorerSavedViewUpdateOptions,
    ExplorerUrlFilter,
)
from ..utils import valid_string_id
from ._base import _Service


def _query_params(options: ExplorerQueryOptions) -> dict[str, Any]:
    params = options.model_dump(
        by_alias=True,
        exclude_none=True,
        exclude={"filters"},
        mode="json",
    )
    if options.filters:
        for flt in options.filters:
            params[
                f"filter[{flt.index}][{flt.field}][{flt.operator}][{flt.value_index}]"
            ] = flt.value
    return params


def _parse_row(item: dict[str, Any]) -> ExplorerRow:
    return ExplorerRow.model_validate(item)


def _saved_query_to_api_shape(raw_query: dict[str, Any]) -> dict[str, Any]:
    """Transform normalized saved-query payload to API-accepted create/update shape."""
    query = dict(raw_query)
    raw_filter = query.get("filter")
    if isinstance(raw_filter, list):
        mapped_filters: list[dict[str, Any]] = []
        for entry in raw_filter:
            if not isinstance(entry, dict):
                continue
            # Already API-compatible map style.
            if "field" not in entry or "operator" not in entry:
                mapped_filters.append(entry)
                continue
            field = str(entry.get("field", "")).replace("-", "_")
            operator = str(entry.get("operator", ""))
            values = entry.get("value", [])
            if not isinstance(values, list):
                values = [values]
            mapped_filters.append({field: {operator: [str(v) for v in values]}})
        query["filter"] = mapped_filters
    return query


def _normalize_saved_query(
    raw_query: dict[str, Any], raw_query_type: str | None
) -> dict[str, Any]:
    """Normalize API variants of saved-query payloads to model shape."""
    query = dict(raw_query)

    if "type" not in query and raw_query_type:
        query["type"] = raw_query_type

    raw_filter = query.get("filter")
    if isinstance(raw_filter, list):
        normalized_filters: list[dict[str, Any]] = []
        for entry in raw_filter:
            # Variant A (documented): {"field": "...", "operator": "...", "value": [...]}
            if isinstance(entry, dict) and "field" in entry and "operator" in entry:
                value = entry.get("value")
                if value is None:
                    value = []
                if not isinstance(value, list):
                    value = [str(value)]
                normalized_filters.append(
                    {
                        "field": str(entry["field"]).replace("-", "_"),
                        "operator": str(entry["operator"]),
                        "value": [str(v) for v in value],
                    }
                )
                continue

            # Variant B (observed): {"workspace-name": {"contains": ["foo"]}}
            if isinstance(entry, dict):
                for field_name, operators in entry.items():
                    if not isinstance(operators, dict):
                        continue
                    for operator, values in operators.items():
                        vals = values if isinstance(values, list) else [values]
                        normalized_filters.append(
                            {
                                "field": str(field_name).replace("-", "_"),
                                "operator": str(operator),
                                "value": [str(v) for v in vals],
                            }
                        )
        query["filter"] = normalized_filters

    raw_fields = query.get("fields")
    # Some responses return fields as {"workspaces": [...]}.
    if isinstance(raw_fields, dict):
        list_values: list[str] = []
        for value in raw_fields.values():
            if isinstance(value, list):
                list_values.extend(str(v) for v in value)
        query["fields"] = list_values

    return query


def _parse_saved_view(item: dict[str, Any]) -> ExplorerSavedView:
    attrs = item.get("attributes", {})
    query_type = attrs.get("query-type")
    query = attrs.get("query", {})
    if not isinstance(query, dict):
        query = {}

    return ExplorerSavedView.model_validate(
        {
            "id": item.get("id"),
            "name": attrs.get("name"),
            "created-at": attrs.get("created-at"),
            "query": _normalize_saved_query(query, query_type),
            "query-type": query_type,
        }
    )


def _deleted_saved_view_fallback(view_id: str) -> ExplorerSavedView:
    """Build a minimal saved view when delete responses have no body."""
    return ExplorerSavedView.model_validate(
        {
            "id": view_id,
            "name": "",
            "query-type": "workspaces",
            "query": {"type": "workspaces"},
        }
    )


def _query_options_from_saved_view(
    saved_view: ExplorerSavedView,
) -> ExplorerQueryOptions:
    """Convert a saved view query into ExplorerQueryOptions."""
    query = saved_view.query
    filters: list[ExplorerUrlFilter] = []
    if query.filter:
        for idx, flt in enumerate(query.filter):
            for value_index, value in enumerate(flt.value or []):
                filters.append(
                    ExplorerUrlFilter(
                        index=idx,
                        field=flt.field,
                        operator=flt.operator,
                        value=str(value),
                        value_index=value_index,
                    )
                )
    return ExplorerQueryOptions.model_validate(
        {
            "type": saved_view.query_type,
            "sort": ",".join(query.sort) if query.sort else None,
            "fields": ",".join(query.fields) if query.fields else None,
            "filters": filters or None,
        }
    )


def _rows_to_csv(rows: list[ExplorerRow]) -> str:
    """Build CSV from Explorer rows attributes."""
    if not rows:
        return ""
    keys: set[str] = set()
    for row in rows:
        keys.update(row.attributes.keys())
    fieldnames = sorted(keys)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.attributes.get(k, "") for k in fieldnames})
    return buf.getvalue()


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
        attrs = options.model_dump(by_alias=True, exclude_none=True, mode="json")
        raw_query = attrs.get("query")
        if isinstance(raw_query, dict):
            attrs["query"] = _saved_query_to_api_shape(raw_query)
        body = {
            "data": {
                "type": "explorer-saved-queries",
                "attributes": attrs,
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
        attrs = options.model_dump(by_alias=True, exclude_none=True, mode="json")
        raw_query = attrs.get("query")
        if isinstance(raw_query, dict):
            attrs["query"] = _saved_query_to_api_shape(raw_query)
        body = {
            "data": {
                "type": "explorer-saved-queries",
                "id": view_id,
                "attributes": attrs,
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
        raw_text = (resp.text or "").strip()
        if not raw_text:
            return _deleted_saved_view_fallback(view_id)

        try:
            payload = resp.json()
        except ValueError:
            return _deleted_saved_view_fallback(view_id)

        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            return _parse_saved_view(payload["data"])
        return _deleted_saved_view_fallback(view_id)

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
        try:
            resp = self.t.request("GET", path)
            return resp.text
        except (NotFound, ServerError):
            pass

        try:
            saved_view = self.read_saved_view(organization, view_id)
            options = _query_options_from_saved_view(saved_view)
            return self.export_csv(organization, options)
        except (NotFound, ServerError):
            rows = list(self.saved_view_results(organization, view_id))
            return _rows_to_csv(rows)
