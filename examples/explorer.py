#!/usr/bin/env python3
# Copyright IBM Corp. 2025, 2026
# SPDX-License-Identifier: MPL-2.0

"""Detailed sample driver for ``TFEClient.explorer``.

Install the package in editable mode (``pip install -e .`` from the repo root) before
running: ``python examples/explorer.py``.

This example demonstrates all 9 Explorer service methods:

1) ``query(organization, options)``
2) ``export_csv(organization, options)``
3) ``list_saved_views(organization)``
4) ``read_saved_view(organization, view_id)``
5) ``saved_view_results(organization, view_id)``
6) ``saved_view_results_csv(organization, view_id)``
7) ``create_saved_view(organization, options)``
8) ``update_saved_view(organization, view_id, options)``
9) ``delete_saved_view(organization, view_id)``

Method parameter reference (complete):

1) ``query(organization, options)``
- ``organization`` (required, ``str``): Terraform organization name.
- ``options`` (required, ``ExplorerQueryOptions``):
  - ``view_type`` / alias ``type`` (required, ``ExplorerViewType``):
    ``workspaces``, ``tf_versions``, ``providers``, ``modules``, ``resources``.
  - ``sort`` (optional, ``str``): comma-separated fields; prefix each field with ``-``
    for descending order.
  - ``fields`` (optional, ``str``): comma-separated list of fields to return.
  - ``page_number`` / alias ``page[number]`` (optional, ``int`` >= 1).
  - ``page_size`` / alias ``page[size]`` (optional, ``int`` in [1, 100]).
  - ``filters`` (optional, ``list[ExplorerUrlFilter]``).

2) ``export_csv(organization, options)``
- Same parameters as ``query``.
- Returns full unpaged CSV text.

3) ``list_saved_views(organization)``
- ``organization`` (required, ``str``).

4) ``read_saved_view(organization, view_id)``
- ``organization`` (required, ``str``).
- ``view_id`` (required, ``str``): saved view identifier.

5) ``saved_view_results(organization, view_id)``
- ``organization`` (required, ``str``).
- ``view_id`` (required, ``str``).

6) ``saved_view_results_csv(organization, view_id)``
- ``organization`` (required, ``str``).
- ``view_id`` (required, ``str``).

7) ``create_saved_view(organization, options)``
- ``organization`` (required, ``str``).
- ``options`` (required, ``ExplorerSavedViewCreateOptions``):
  - ``name`` (required, ``str``).
  - ``query_type`` / alias ``query-type`` (required, ``ExplorerViewType``).
  - ``query`` (required, ``ExplorerSavedQuery``):
    - ``query_type`` / alias ``type`` (required, ``ExplorerViewType``).
    - ``filter`` (optional, ``list[ExplorerSavedQueryFilter]``).
    - ``fields`` (optional, ``list[str]``).
    - ``sort`` (optional, ``list[str]``).

8) ``update_saved_view(organization, view_id, options)``
- ``organization`` (required, ``str``).
- ``view_id`` (required, ``str``).
- ``options`` (required, ``ExplorerSavedViewUpdateOptions``):
  - ``name`` (required, ``str``).
  - ``query`` (required, ``ExplorerSavedQuery``) with the same fields as above.

9) ``delete_saved_view(organization, view_id)``
- ``organization`` (required, ``str``).
- ``view_id`` (required, ``str``).

Filter object parameter reference:
- ``ExplorerUrlFilter(index, field, operator, value, value_index=0)``
  - ``index`` (required, ``int`` >= 0): filter index in URL query.
  - ``field`` (required, ``str``): target column in snake_case.
  - ``operator`` (required, ``str``): for example ``contains``, ``is``, ``is_not``,
    ``gt``, ``lt``, ``gteq``, ``lteq``, ``is_empty``, ``is_not_empty``,
    ``is_before``, ``is_after``.
  - ``value`` (required, ``str``): filter comparison value.
  - ``value_index`` (optional, ``int`` >= 0, default ``0``).

Saved query filter parameter reference:
- ``ExplorerSavedQueryFilter(field, operator, value)``
  - ``field`` (required, ``str``).
  - ``operator`` (required, ``str``).
  - ``value`` (required, ``list[str]``).

Execution layout:
- Sections 1-3 always run (read-only operations).
- Sections 4-6 run only when ``TFE_EXPLORER_VIEW_ID`` is set.
- Section 7 runs only when ``TFE_EXPLORER_DEMO_MUTATIONS=1`` because it creates,
  updates, and deletes a real saved view.

Input model notes used by this example:
- ``ExplorerQueryOptions``:
  - ``view_type`` (required): one of ``workspaces``, ``tf_versions``, ``providers``,
    ``modules``, ``resources``.
  - ``sort`` (optional): field name; prefix with ``-`` for descending.
  - ``fields`` (optional): comma-separated field list.
  - ``filters`` (optional): list of ``ExplorerUrlFilter`` entries.
- ``ExplorerUrlFilter``:
  - ``index``: filter group index in URL shape.
  - ``field``: target column (snake_case).
  - ``operator``: filter operator (for example ``contains``, ``is``, ``gt``).
  - ``value``: filter value string.
  - ``value_index``: usually ``0``.
- ``ExplorerSavedViewCreateOptions``:
  - ``name``, ``query_type``, ``query``.
- ``ExplorerSavedViewUpdateOptions``:
  - ``name``, ``query``.
- ``ExplorerSavedQuery``:
  - ``query_type``, optional ``filter``, optional ``fields``, optional ``sort``.
- ``ExplorerSavedQueryFilter``:
  - ``field``, ``operator``, ``value`` (list of strings).

Environment
-----------
``TFE_TOKEN`` (required)
    API token with Explorer access for the target organization.

``TFE_ADDRESS`` (optional)
    Defaults to ``https://app.terraform.io``.

``TFE_ORGANIZATION`` (optional)
    Organization name; replace the placeholder when testing against a real org.

``TFE_EXPLORER_VIEW_ID`` (optional)
    Saved view id (``sq-...``) to exercise read, results iterator, and results CSV.

``TFE_EXPLORER_DEMO_MUTATIONS``
    Set to ``1`` to run the create/update/delete demo (uses a unique view name per run).
"""

from __future__ import annotations

import os
import sys
import uuid

from pytfe import TFEClient, TFEConfig
from pytfe.errors import TFEError
from pytfe.models import (
    ExplorerQueryOptions,
    ExplorerSavedQuery,
    ExplorerSavedQueryFilter,
    ExplorerSavedViewCreateOptions,
    ExplorerSavedViewUpdateOptions,
    ExplorerUrlFilter,
    ExplorerViewType,
)


def main() -> None:
    """Run all Explorer scenarios with clear inputs for each method call."""
    token = os.getenv("TFE_TOKEN")
    if not token:
        print("Error: TFE_TOKEN is not set.")
        sys.exit(1)

    address = os.getenv("TFE_ADDRESS", "https://app.terraform.io")
    org = os.getenv("TFE_ORGANIZATION", "your-org-name")
    view_id = os.getenv("TFE_EXPLORER_VIEW_ID")
    demo_mutations = os.getenv("TFE_EXPLORER_DEMO_MUTATIONS") == "1"

    client = TFEClient(TFEConfig(address=address, token=token))

    print(f"Explorer example — organization: {org!r}")
    print("=" * 60)

    # 1) query(organization, options)
    # Inputs:
    # - organization: org name string (``org``)
    # - options: ExplorerQueryOptions
    #   - view_type: selects Explorer dataset/view
    #   - sort: descending by workspace_name
    #   - filters: one URL-style filter expression
    # Output:
    # - Iterator[ExplorerRow], each row containing id/type/attributes
    print("\n1. Query workspaces view (first 5 rows)")
    print("-" * 60)
    query_opts = ExplorerQueryOptions(
        view_type=ExplorerViewType.WORKSPACES,
        sort="-workspace_name",
        filters=[
            ExplorerUrlFilter(
                index=0,
                field="workspace_name",
                operator="contains",
                value="42",
            ),
        ],
    )
    try:
        for i, row in enumerate(client.explorer.query(org, query_opts)):
            if i >= 5:
                break
            name = row.attributes.get("workspace-name") or row.attributes.get(
                "workspace_name"
            )
            print(f"  {row.id}  workspace-name={name!r}")
    except TFEError as e:
        print(f"  TFE API error: {e}")
    except Exception as e:
        print(f"  Error: {e}")

    # 2) export_csv(organization, options)
    # Inputs:
    # - organization: org name
    # - options: ExplorerQueryOptions (minimum required input: view_type)
    # Output:
    # - CSV string for full unpaged query result
    print("\n2. CSV export (first 400 characters)")
    print("-" * 60)
    try:
        csv_text = client.explorer.export_csv(
            org, ExplorerQueryOptions(view_type=ExplorerViewType.WORKSPACES)
        )
        print(csv_text[:400] + ("..." if len(csv_text) > 400 else ""))
    except TFEError as e:
        print(f"  TFE API error: {e}")
    except Exception as e:
        print(f"  Error: {e}")

    # 3) list_saved_views(organization)
    # Inputs:
    # - organization: org name
    # Output:
    # - Iterator[ExplorerSavedView]
    print("\n3. List saved views")
    print("-" * 60)
    try:
        for sv in client.explorer.list_saved_views(org):
            print(f"  {sv.id}  {sv.name!r}  query-type={sv.query_type!r}")
    except TFEError as e:
        print(f"  TFE API error: {e}")
    except Exception as e:
        print(f"  Error: {e}")

    if view_id:
        # 4) read_saved_view(organization, view_id)
        # Inputs:
        # - organization: org name
        # - view_id: saved view identifier (``esv-...`` in many tenants)
        # Output:
        # - ExplorerSavedView with name/query/query_type
        print("\n4. Read saved view")
        print("-" * 60)
        try:
            sv = client.explorer.read_saved_view(org, view_id)
            print(f"  {sv.id}  {sv.name!r}  query={sv.query!r}")
        except TFEError as e:
            print(f"  TFE API error: {e}")

        # 5) saved_view_results(organization, view_id)
        # Inputs:
        # - organization: org name
        # - view_id: saved view identifier
        # Output:
        # - Iterator[ExplorerRow] from re-executing current saved query definition
        print("\n5. Saved view results (first 3 rows)")
        print("-" * 60)
        try:
            for i, row in enumerate(client.explorer.saved_view_results(org, view_id)):
                if i >= 3:
                    break
                print(f"  {row.id}  type={row.row_type!r}")
        except TFEError as e:
            print(f"  TFE API error: {e}")

        # 6) saved_view_results_csv(organization, view_id)
        # Inputs:
        # - organization: org name
        # - view_id: saved view identifier
        # Output:
        # - CSV string. SDK includes fallback paths if direct CSV endpoint is unavailable.
        print("\n6. Saved view results as CSV (first 300 chars)")
        print("-" * 60)
        try:
            csv_sv = client.explorer.saved_view_results_csv(org, view_id)
            print(csv_sv[:300] + ("..." if len(csv_sv) > 300 else ""))
        except TFEError as e:
            print(f"  TFE API error: {e}")
            print(
                "  Hint: ``not found`` often means ``TFE_EXPLORER_VIEW_ID`` was deleted or "
                "belongs to another org. pytfe also falls back to ``export_csv`` and to CSV "
                "built from ``saved_view_results``; if step 5 worked, reinstall editable pytfe."
            )
    else:
        print("\n4–6. Skipped (set TFE_EXPLORER_VIEW_ID to exercise read/results/csv)")
        print("-" * 60)

    if demo_mutations:
        suffix = uuid.uuid4().hex[:8]
        base_name = f"python-tfe-explorer-example-{suffix}"
        # 7) create_saved_view(organization, options)
        # 8) update_saved_view(organization, view_id, options)
        # 9) delete_saved_view(organization, view_id)
        #
        # Inputs:
        # - organization: org name
        # - create options:
        #   - name: unique per run
        #   - query_type: workspaces
        #   - query.filter: workspace_name contains "test"
        # - update options:
        #   - name: updated name
        #   - query.filter: workspace_name contains "demo"
        #
        # Outputs:
        # - created: ExplorerSavedView (uses returned ``id`` for next calls)
        # - updated: ExplorerSavedView
        # - deleted: ExplorerSavedView (or minimal object if API delete response is empty)
        print(f"\n7. Demo mutations — create / update / delete ({base_name!r})")
        print("-" * 60)
        try:
            create_opts = ExplorerSavedViewCreateOptions(
                name=base_name,
                query_type=ExplorerViewType.WORKSPACES,
                query=ExplorerSavedQuery(
                    query_type=ExplorerViewType.WORKSPACES,
                    filter=[
                        ExplorerSavedQueryFilter(
                            field="workspace_name",
                            operator="contains",
                            value=["test"],
                        )
                    ],
                ),
            )
            created = client.explorer.create_saved_view(org, create_opts)
            print(f"  Created: {created.id}")

            update_opts = ExplorerSavedViewUpdateOptions(
                name=f"{base_name}-updated",
                query=ExplorerSavedQuery(
                    query_type=ExplorerViewType.WORKSPACES,
                    filter=[
                        ExplorerSavedQueryFilter(
                            field="workspace_name",
                            operator="contains",
                            value=["demo"],
                        )
                    ],
                ),
            )
            updated = client.explorer.update_saved_view(org, created.id, update_opts)
            print(f"  Updated: {updated.name!r}")

            deleted = client.explorer.delete_saved_view(org, created.id)
            print(f"  Deleted: {deleted.id}")
        except TFEError as e:
            print(f"  TFE API error: {e}")
            sys.exit(1)
    else:
        print(
            "\n7. Skipped (set TFE_EXPLORER_DEMO_MUTATIONS=1 to run create/update/delete)"
        )
        print("-" * 60)

    print("\nDone.")


if __name__ == "__main__":
    main()
