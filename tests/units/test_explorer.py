# Copyright IBM Corp. 2025, 2026
# SPDX-License-Identifier: MPL-2.0

"""Tests for Explorer models, ``_params_from_query_options``, and ``Explorer`` HTTP calls.

All network I/O is stubbed via ``client._transport.request`` (or ``Explorer(Mock())`` for
parsers). No Terraform Enterprise instance is contacted.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

from pytfe import TFEClient, TFEConfig
from pytfe.errors import InvalidExplorerSavedViewIDError, InvalidOrgError
from pytfe.models.explorer import (
    ExplorerQueryOptions,
    ExplorerRow,
    ExplorerSavedQuery,
    ExplorerSavedQueryFilter,
    ExplorerSavedViewCreateOptions,
    ExplorerSavedViewUpdateOptions,
    ExplorerUrlFilter,
    ExplorerViewType,
)
from pytfe.resources.explorer import Explorer, _params_from_query_options


class TestExplorerModels:
    """Test Explorer Pydantic models."""

    def test_explorer_row_from_api(self) -> None:
        """Parse a typical Explorer API row."""
        row = ExplorerRow.model_validate(
            {
                "id": "ws-abc",
                "type": "visibility-workspace",
                "attributes": {"workspace-name": "api", "drifted": False},
            }
        )
        assert row.id == "ws-abc"
        assert row.row_type == "visibility-workspace"
        assert row.attributes["workspace-name"] == "api"

    def test_params_from_query_options_with_filters(self) -> None:
        """URL filter keys match the API shape."""
        opts = ExplorerQueryOptions(
            view_type=ExplorerViewType.WORKSPACES,
            sort="-workspace_name",
            filters=[
                ExplorerUrlFilter(
                    index=0,
                    field="workspace_name",
                    operator="contains",
                    value="test",
                )
            ],
        )
        params = _params_from_query_options(opts)
        assert params["type"] == "workspaces"
        assert params["sort"] == "-workspace_name"
        assert params["filter[0][workspace_name][contains][0]"] == "test"


class TestExplorerService:
    """Test Explorer resource methods."""

    @pytest.fixture
    def client(self) -> TFEClient:
        return TFEClient(TFEConfig(address="https://test.terraform.io", token="x"))

    def test_query_invalid_org(self, client: TFEClient) -> None:
        with pytest.raises(InvalidOrgError):
            list(
                client.explorer.query(
                    "",
                    ExplorerQueryOptions(view_type=ExplorerViewType.WORKSPACES),
                )
            )

    def test_query_one_page(self, client: TFEClient) -> None:
        mock = Mock()
        mock.json.return_value = {
            "data": [
                {
                    "id": "ws-1",
                    "type": "visibility-workspace",
                    "attributes": {"workspace-name": "a"},
                }
            ],
            "meta": {
                "pagination": {
                    "current-page": 1,
                    "total-pages": 1,
                    "total-count": 1,
                }
            },
        }
        client._transport.request = MagicMock(return_value=mock)

        rows = list(
            client.explorer.query(
                "acme",
                ExplorerQueryOptions(view_type=ExplorerViewType.MODULES),
            )
        )
        assert len(rows) == 1
        assert rows[0].id == "ws-1"
        client._transport.request.assert_called_once()
        call = client._transport.request.call_args
        assert call[0][0] == "GET"
        assert call[0][1] == "/api/v2/organizations/acme/explorer"
        assert call[1]["params"]["type"] == "modules"
        assert call[1]["params"]["page[number]"] == "1"
        assert call[1]["params"]["page[size]"] == "100"

    def test_export_csv(self, client: TFEClient) -> None:
        mock = Mock()
        mock.text = "a,b\n1,2\n"
        client._transport.request = MagicMock(return_value=mock)

        out = client.explorer.export_csv(
            "acme",
            ExplorerQueryOptions(view_type=ExplorerViewType.PROVIDERS),
        )
        assert out == "a,b\n1,2\n"
        call = client._transport.request.call_args
        assert call[0][1] == "/api/v2/organizations/acme/explorer/export/csv"
        assert call[1]["params"]["type"] == "providers"

    def test_list_saved_views(self, client: TFEClient) -> None:
        mock = Mock()
        mock.json.return_value = {
            "data": [
                {
                    "id": "sq-1",
                    "type": "explorer-saved-queries",
                    "attributes": {
                        "name": "q1",
                        "created-at": "2024-01-01T00:00:00Z",
                        "query-type": "workspaces",
                        "query": {"type": "workspaces"},
                    },
                }
            ],
            "meta": {
                "pagination": {
                    "current-page": 1,
                    "total-pages": 1,
                }
            },
        }
        client._transport.request = MagicMock(return_value=mock)

        views = list(client.explorer.list_saved_views("acme"))
        assert len(views) == 1
        assert views[0].id == "sq-1"
        assert views[0].name == "q1"
        assert views[0].query_type == "workspaces"

    def test_create_saved_view(self, client: TFEClient) -> None:
        mock = Mock()
        mock.json.return_value = {
            "data": {
                "id": "sq-new",
                "type": "explorer-saved-queries",
                "attributes": {
                    "name": "n",
                    "query-type": "workspaces",
                    "query": {"type": "workspaces", "filter": []},
                },
            }
        }
        client._transport.request = MagicMock(return_value=mock)

        opts = ExplorerSavedViewCreateOptions(
            name="n",
            query_type=ExplorerViewType.WORKSPACES,
            query=ExplorerSavedQuery(type="workspaces", filter=[]),
        )
        v = client.explorer.create_saved_view("acme", opts)
        assert v.id == "sq-new"
        body = client._transport.request.call_args[1]["json_body"]
        assert body["data"]["type"] == "explorer-saved-queries"
        assert body["data"]["attributes"]["name"] == "n"
        assert body["data"]["attributes"]["query-type"] == "workspaces"

    def test_read_saved_view_invalid_id(self, client: TFEClient) -> None:
        with pytest.raises(InvalidExplorerSavedViewIDError):
            client.explorer.read_saved_view("acme", "")

    def test_read_saved_view(self, client: TFEClient) -> None:
        mock = Mock()
        mock.json.return_value = {
            "data": {
                "id": "sq-read",
                "type": "explorer-saved-queries",
                "attributes": {
                    "name": "my-view",
                    "created-at": "2024-06-01T12:00:00Z",
                    "query-type": "workspaces",
                    "query": {"type": "workspaces", "filter": []},
                },
            }
        }
        client._transport.request = MagicMock(return_value=mock)

        v = client.explorer.read_saved_view("acme", "sq-read")
        assert v.id == "sq-read"
        assert v.name == "my-view"
        assert v.query_type == "workspaces"
        call = client._transport.request.call_args
        assert call[0][0] == "GET"
        assert call[0][1] == "/api/v2/organizations/acme/explorer/views/sq-read"

    def test_update_saved_view(self, client: TFEClient) -> None:
        mock = Mock()
        mock.json.return_value = {
            "data": {
                "id": "sq-upd",
                "type": "explorer-saved-queries",
                "attributes": {
                    "name": "updated",
                    "query-type": "workspaces",
                    "query": {
                        "type": "workspaces",
                        "filter": [
                            {
                                "field": "workspace_name",
                                "operator": "contains",
                                "value": ["x"],
                            }
                        ],
                    },
                },
            }
        }
        client._transport.request = MagicMock(return_value=mock)

        opts = ExplorerSavedViewUpdateOptions(
            name="updated",
            query=ExplorerSavedQuery(
                type="workspaces",
                filter=[
                    ExplorerSavedQueryFilter(
                        field="workspace_name",
                        operator="contains",
                        value=["x"],
                    )
                ],
            ),
        )
        v = client.explorer.update_saved_view("acme", "sq-upd", opts)
        assert v.name == "updated"
        body = client._transport.request.call_args[1]["json_body"]
        assert body["data"]["type"] == "explorer-saved-queries"
        assert body["data"]["id"] == "sq-upd"
        assert body["data"]["attributes"]["name"] == "updated"
        call = client._transport.request.call_args
        assert call[0][0] == "PATCH"
        assert call[0][1] == "/api/v2/organizations/acme/explorer/views/sq-upd"

    def test_delete_saved_view(self, client: TFEClient) -> None:
        mock = Mock()
        mock.json.return_value = {
            "data": {
                "id": "sq-del",
                "type": "explorer-saved-queries",
                "attributes": {
                    "name": "gone",
                    "query-type": "modules",
                    "query": {"type": "modules"},
                },
            }
        }
        client._transport.request = MagicMock(return_value=mock)

        v = client.explorer.delete_saved_view("acme", "sq-del")
        assert v.id == "sq-del"
        call = client._transport.request.call_args
        assert call[0][0] == "DELETE"
        assert call[0][1] == "/api/v2/organizations/acme/explorer/views/sq-del"

    def test_saved_view_results(self, client: TFEClient) -> None:
        mock = Mock()
        mock.json.return_value = {
            "data": [
                {
                    "id": "ws-x",
                    "type": "visibility-workspace",
                    "attributes": {},
                }
            ],
            "meta": {"pagination": {"current-page": 1, "total-pages": 1}},
        }
        client._transport.request = MagicMock(return_value=mock)

        rows = list(client.explorer.saved_view_results("acme", "sq-1"))
        assert len(rows) == 1
        assert rows[0].id == "ws-x"
        call = client._transport.request.call_args
        assert call[0][1] == "/api/v2/organizations/acme/explorer/views/sq-1/results"

    def test_saved_view_results_csv(self, client: TFEClient) -> None:
        mock = Mock()
        mock.text = "h1,h2\nv1,v2\n"
        client._transport.request = MagicMock(return_value=mock)

        out = client.explorer.saved_view_results_csv("acme", "sq-csv")
        assert out == "h1,h2\nv1,v2\n"
        call = client._transport.request.call_args
        assert call[0][0] == "GET"
        assert call[0][1] == "/api/v2/organizations/acme/explorer/views/sq-csv/csv"

    def test_export_csv_invalid_org(self, client: TFEClient) -> None:
        with pytest.raises(InvalidOrgError):
            client.explorer.export_csv(
                "",
                ExplorerQueryOptions(view_type=ExplorerViewType.WORKSPACES),
            )

    def test_list_saved_views_invalid_org(self, client: TFEClient) -> None:
        with pytest.raises(InvalidOrgError):
            list(client.explorer.list_saved_views(""))

    def test_parse_helpers(self) -> None:
        svc = Explorer(Mock())
        row = svc._parse_row(
            {"id": "w", "type": "visibility-workspace", "attributes": {}}
        )
        assert isinstance(row, ExplorerRow)
