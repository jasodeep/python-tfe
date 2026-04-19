# Copyright IBM Corp. 2025, 2026
# SPDX-License-Identifier: MPL-2.0

"""Explorer API request/response models (HCP Terraform / Terraform Enterprise).

Explorer returns organization-scoped visibility rows (workspaces, Terraform versions,
registry providers, modules). The service speaks JSON:API for saved views; ad-hoc
queries use query-string parameters documented here:

https://developer.hashicorp.com/terraform/cloud-docs/api-docs/explorer

This module defines two filter representations:

* :class:`ExplorerUrlFilter` — encodes the ``filter[i][field][op][0]=...`` query shape
  used by ``GET .../explorer`` and ``GET .../explorer/export/csv``.
* :class:`ExplorerSavedQueryFilter` — elements of the ``query.filter`` array in
  create/update saved-view JSON bodies. Same logical filters; different encoding.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExplorerViewType(str, Enum):
    """Required ``type`` parameter for Explorer views (query string and saved-query body)."""

    WORKSPACES = "workspaces"
    TF_VERSIONS = "tf_versions"
    PROVIDERS = "providers"
    MODULES = "modules"


class ExplorerUrlFilter(BaseModel):
    """One ``filter[...]`` clause for Explorer GET requests (query or CSV export).

    Encoding follows ``filter[<n>][<field>][<operator>][<value_index>]=<value>``.
    Reuse ``index`` across clauses that must all match (AND). Increment ``index`` when
    starting a new filter group. Field names are view-specific and snake_case per API
    documentation for the active :class:`ExplorerViewType`.
    """

    model_config = ConfigDict(populate_by_name=True)

    index: int = Field(
        ...,
        ge=0,
        description="Filter group index; AND within a group, separate groups by index.",
    )
    field: str = Field(
        ..., description="Snake_case field name for the current view type."
    )
    operator: str = Field(
        ...,
        description='API operator (e.g. "is", "contains", "does not contain").',
    )
    value: str = Field(..., description="Operand string.")
    value_index: int = Field(
        0,
        ge=0,
        description="Fourth path segment; the API reserves this and expects 0.",
    )


class ExplorerQueryOptions(BaseModel):
    """Parameters for ad-hoc Explorer GET requests (JSON result or CSV export).

    Used by ``Explorer.query`` and ``Explorer.export_csv``. ``view_type`` becomes the
    ``type`` query argument. Filters are applied in
    ``pytfe.resources.explorer._params_from_query_options`` (not via a plain model dump)
    because each clause becomes a distinct query key.
    """

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    view_type: ExplorerViewType = Field(
        ...,
        serialization_alias="type",
        description="Catalog: workspaces, tf_versions, providers, or modules.",
    )
    sort: str | None = Field(
        None,
        description="Snake_case column; leading '-' denotes descending order.",
    )
    fields: str | None = Field(
        None,
        description="Comma-separated snake_case columns to include in the response.",
    )
    filters: list[ExplorerUrlFilter] | None = Field(
        None,
        description="Optional URL filter clauses.",
    )


class ExplorerRow(BaseModel):
    """Single visibility record from Explorer JSON or saved-view results.

    The upstream payload uses JSON ``type`` (e.g. ``visibility-workspace``) and
    kebab-case keys inside ``attributes``. :attr:`attributes` is left as a mapping so
    callers handle schema variance across view types without breaking on new fields.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    row_type: str = Field(..., alias="type")
    attributes: dict[str, Any] = Field(default_factory=dict)


class ExplorerSavedQueryFilter(BaseModel):
    """One element of the ``filter`` array inside a saved view ``query`` object."""

    model_config = ConfigDict(populate_by_name=True)

    field: str
    operator: str
    value: list[str]


class ExplorerSavedQuery(BaseModel):
    """``query`` attribute for saved-view create/update (nested structure, not query string)."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(
        ...,
        description="View discriminator (e.g. workspaces, modules).",
    )
    filter: list[ExplorerSavedQueryFilter] | None = None
    fields: list[str] | None = None
    sort: list[str] | None = None


class ExplorerSavedView(BaseModel):
    """Saved Explorer view (``explorer-saved-queries`` resource)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    created_at: datetime | None = Field(None, alias="created-at")
    query: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque server payload: filters, sort, nested type, etc.",
    )
    query_type: str = Field(
        ...,
        alias="query-type",
        description="View label on the resource; typically matches ``query.type``.",
    )


class ExplorerSavedViewCreateOptions(BaseModel):
    """Attributes for ``POST /api/v2/organizations/:org/explorer/views``."""

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    name: str
    query_type: ExplorerViewType | str = Field(
        ...,
        serialization_alias="query-type",
        description="Serialized as ``query-type``; aligns with ``query.type``.",
    )
    query: ExplorerSavedQuery


class ExplorerSavedViewUpdateOptions(BaseModel):
    """Attributes for ``PATCH /api/v2/organizations/:org/explorer/views/:id``."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    query: ExplorerSavedQuery
