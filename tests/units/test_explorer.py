# Copyright IBM Corp. 2025, 2026
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for Explorer API resource."""

from unittest.mock import Mock

import pytest

from pytfe.errors import InvalidExplorerSavedViewIDError, InvalidOrgError
from pytfe.models import (
    ExplorerQueryOptions,
    ExplorerSavedQuery,
    ExplorerSavedQueryFilter,
    ExplorerSavedViewCreateOptions,
    ExplorerSavedViewUpdateOptions,
    ExplorerUrlFilter,
    ExplorerViewType,
)
from pytfe.resources.explorer import Explorer


@pytest.fixture
def mock_transport():
    return Mock()


@pytest.fixture
def explorer_service(mock_transport):
    return Explorer(mock_transport)


def _row_payload(row_id: str) -> dict:
    return {
        "id": row_id,
        "type": "visibility-workspace",
        "attributes": {"workspace-name": "demo-workspace"},
    }


def _saved_view_payload(view_id: str) -> dict:
    return {
        "id": view_id,
        "type": "explorer-saved-queries",
        "attributes": {
            "name": "my-view",
            "created-at": "2024-10-11T16:18:51.442Z",
            "query-type": "workspaces",
            "query": {
                "type": "workspaces",
                "filter": [
                    {
                        "field": "workspace_name",
                        "operator": "contains",
                        "value": ["child"],
                    }
                ],
            },
        },
    }


class TestExplorerQuery:
    def test_query_with_filter_and_pagination(self, explorer_service, mock_transport):
        first = Mock()
        first.json.return_value = {"data": [_row_payload("ws-1")]}
        second = Mock()
        second.json.return_value = {"data": []}
        mock_transport.request.side_effect = [first, second]

        options = ExplorerQueryOptions(
            view_type=ExplorerViewType.WORKSPACES,
            sort="-workspace_name",
            fields="workspace_name,organization_name",
            page_size=1,
            filters=[
                ExplorerUrlFilter(
                    index=0,
                    field="workspace_name",
                    operator="contains",
                    value="test",
                )
            ],
        )

        rows = list(explorer_service.query("acme", options))
        assert len(rows) == 1
        assert rows[0].id == "ws-1"
        assert rows[0].row_type == "visibility-workspace"

        first_call = mock_transport.request.call_args_list[0]
        assert first_call[0][0] == "GET"
        assert first_call[0][1] == "/api/v2/organizations/acme/explorer"
        params = first_call[1]["params"]
        assert params["type"] == "workspaces"
        assert params["sort"] == "-workspace_name"
        assert params["fields"] == "workspace_name,organization_name"
        assert params["page[size]"] == 1
        assert params["filter[0][workspace_name][contains][0]"] == "test"

    def test_query_invalid_org(self, explorer_service):
        with pytest.raises(InvalidOrgError):
            list(
                explorer_service.query(
                    "",
                    ExplorerQueryOptions(view_type=ExplorerViewType.WORKSPACES),
                )
            )

    def test_export_csv(self, explorer_service, mock_transport):
        response = Mock()
        response.text = "workspace_name\nexample\n"
        mock_transport.request.return_value = response

        csv_text = explorer_service.export_csv(
            "acme", ExplorerQueryOptions(view_type=ExplorerViewType.WORKSPACES)
        )

        assert "workspace_name" in csv_text
        mock_transport.request.assert_called_once_with(
            "GET",
            "/api/v2/organizations/acme/explorer/export/csv",
            params={"type": "workspaces"},
        )


class TestExplorerSavedViews:
    def test_list_saved_views(self, explorer_service, mock_transport):
        response = Mock()
        response.json.return_value = {"data": [_saved_view_payload("sq-1")]}
        mock_transport.request.return_value = response

        views = list(explorer_service.list_saved_views("acme"))
        assert len(views) == 1
        assert views[0].id == "sq-1"
        assert views[0].query_type == ExplorerViewType.WORKSPACES
        assert views[0].query.query_type == ExplorerViewType.WORKSPACES

    def test_create_saved_view(self, explorer_service, mock_transport):
        response = Mock()
        response.json.return_value = {"data": _saved_view_payload("sq-new")}
        mock_transport.request.return_value = response

        options = ExplorerSavedViewCreateOptions(
            name="my-view",
            query_type=ExplorerViewType.WORKSPACES,
            query=ExplorerSavedQuery(
                query_type=ExplorerViewType.WORKSPACES,
                filter=[
                    ExplorerSavedQueryFilter(
                        field="workspace_name", operator="contains", value=["test"]
                    )
                ],
            ),
        )
        view = explorer_service.create_saved_view("acme", options)

        assert view.id == "sq-new"
        call = mock_transport.request.call_args
        assert call[0][0] == "POST"
        assert call[0][1] == "/api/v2/organizations/acme/explorer/views"
        body = call[1]["json_body"]
        assert body["data"]["type"] == "explorer-saved-queries"
        assert body["data"]["attributes"]["query-type"] == "workspaces"

    def test_read_saved_view(self, explorer_service, mock_transport):
        response = Mock()
        response.json.return_value = {"data": _saved_view_payload("sq-1")}
        mock_transport.request.return_value = response

        view = explorer_service.read_saved_view("acme", "sq-1")
        assert view.id == "sq-1"

        mock_transport.request.assert_called_once_with(
            "GET", "/api/v2/organizations/acme/explorer/views/sq-1"
        )

    def test_update_saved_view(self, explorer_service, mock_transport):
        response = Mock()
        response.json.return_value = {"data": _saved_view_payload("sq-1")}
        mock_transport.request.return_value = response

        options = ExplorerSavedViewUpdateOptions(
            name="my-view-updated",
            query=ExplorerSavedQuery(
                query_type=ExplorerViewType.WORKSPACES,
                filter=[
                    ExplorerSavedQueryFilter(
                        field="workspace_name", operator="contains", value=["prod"]
                    )
                ],
            ),
        )
        view = explorer_service.update_saved_view("acme", "sq-1", options)

        assert view.id == "sq-1"
        call = mock_transport.request.call_args
        assert call[0][0] == "PATCH"
        assert call[0][1] == "/api/v2/organizations/acme/explorer/views/sq-1"
        assert call[1]["json_body"]["data"]["id"] == "sq-1"
        assert call[1]["json_body"]["data"]["attributes"]["name"] == "my-view-updated"

    def test_delete_saved_view(self, explorer_service, mock_transport):
        response = Mock()
        response.json.return_value = {"data": _saved_view_payload("sq-1")}
        mock_transport.request.return_value = response

        view = explorer_service.delete_saved_view("acme", "sq-1")
        assert view.id == "sq-1"

        mock_transport.request.assert_called_once_with(
            "DELETE", "/api/v2/organizations/acme/explorer/views/sq-1"
        )

    def test_saved_view_results(self, explorer_service, mock_transport):
        first = Mock()
        first.json.return_value = {"data": [_row_payload("ws-1")]}
        second = Mock()
        second.json.return_value = {"data": []}
        mock_transport.request.side_effect = [first, second]

        rows = list(explorer_service.saved_view_results("acme", "sq-1"))
        assert len(rows) == 1
        assert rows[0].id == "ws-1"

        mock_transport.request.assert_any_call(
            "GET",
            "/api/v2/organizations/acme/explorer/views/sq-1/results",
            params={"page[number]": 1, "page[size]": 100},
        )

    def test_saved_view_results_csv(self, explorer_service, mock_transport):
        response = Mock()
        response.text = "workspace_name\nexample\n"
        mock_transport.request.return_value = response

        csv_text = explorer_service.saved_view_results_csv("acme", "sq-1")
        assert "workspace_name" in csv_text
        mock_transport.request.assert_called_once_with(
            "GET", "/api/v2/organizations/acme/explorer/views/sq-1/csv"
        )

    @pytest.mark.parametrize("org", ["", None])
    def test_saved_view_methods_invalid_org(self, explorer_service, org):
        with pytest.raises(InvalidOrgError):
            list(explorer_service.list_saved_views(org))

        with pytest.raises(InvalidOrgError):
            explorer_service.read_saved_view(org, "sq-1")

    @pytest.mark.parametrize("view_id", ["", None])
    def test_saved_view_methods_invalid_id(self, explorer_service, view_id):
        with pytest.raises(InvalidExplorerSavedViewIDError):
            explorer_service.read_saved_view("acme", view_id)

        with pytest.raises(InvalidExplorerSavedViewIDError):
            explorer_service.update_saved_view(
                "acme",
                view_id,
                ExplorerSavedViewUpdateOptions(
                    name="updated",
                    query=ExplorerSavedQuery(query_type=ExplorerViewType.WORKSPACES),
                ),
            )

        with pytest.raises(InvalidExplorerSavedViewIDError):
            explorer_service.delete_saved_view("acme", view_id)

        with pytest.raises(InvalidExplorerSavedViewIDError):
            list(explorer_service.saved_view_results("acme", view_id))

        with pytest.raises(InvalidExplorerSavedViewIDError):
            explorer_service.saved_view_results_csv("acme", view_id)
