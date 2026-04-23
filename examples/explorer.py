#!/usr/bin/env python3
# Copyright IBM Corp. 2025, 2026
# SPDX-License-Identifier: MPL-2.0

"""Sample driver for ``TFEClient.explorer``.

Install the package in editable mode (``pip install -e .`` from the repo root) before
running: ``python examples/explorer.py``.

Sections 1–3 always run (read-only). Sections 4–6 require ``TFE_EXPLORER_VIEW_ID``.
Section 7 mutates state (create/update/delete one saved view) and runs only when
``TFE_EXPLORER_DEMO_MUTATIONS=1``.

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
    ExplorerViewType,
)


def main() -> None:
    """Execute the scripted scenarios; environment variables gate optional paths."""
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

    # Workspaces view; optional ExplorerUrlFilter in query_opts.filters (see SDK models).
    print("\n1. Query workspaces view (first 5 rows)")
    print("-" * 60)
    query_opts = ExplorerQueryOptions(
        view_type=ExplorerViewType.WORKSPACES,
        sort="-workspace_name",
        # filters=[
        #     ExplorerUrlFilter(
        #         index=0,
        #         field="workspace_name",
        #         operator="contains",
        #         value="prod",
        #     ),
        # ],
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
        print("\n4. Read saved view")
        print("-" * 60)
        try:
            sv = client.explorer.read_saved_view(org, view_id)
            print(f"  {sv.id}  {sv.name!r}  query={sv.query!r}")
        except TFEError as e:
            print(f"  TFE API error: {e}")

        print("\n5. Saved view results (first 3 rows)")
        print("-" * 60)
        try:
            for i, row in enumerate(client.explorer.saved_view_results(org, view_id)):
                if i >= 3:
                    break
                print(f"  {row.id}  type={row.row_type!r}")
        except TFEError as e:
            print(f"  TFE API error: {e}")

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
