from datetime import datetime
from typing import Optional

from nicegui import app, ui

from dashboard.services.api_client import APIClient


def build_cases_page() -> None:
    """Render the main cases dashboard page.

    Displays a header with quick-stats, filter/sort controls, and a sortable
    table of legal cases.  Each pending row has inline action buttons for
    accepting, rejecting, and requesting more information.  The page
    auto-refreshes every 30 seconds.
    """
    token: str = app.storage.user.get("token")
    name: str = app.storage.user.get("name", "Lawyer")
    client = APIClient(token=token)

    ui.query("body").style("background: #f0f4f8")

    with ui.column().classes("w-full min-h-screen"):

        # ── Header ────────────────────────────────────────────────────────────
        with ui.row().classes(
            "w-full items-center justify-between px-6 py-3 bg-[#1a3a6b] shadow-md"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.label("⚖️").classes("text-2xl")
                ui.label("LegalAI").classes("text-xl font-bold text-white tracking-wide")

            with ui.row().classes("items-center gap-3"):
                total_chip = ui.label("Total: —").classes(
                    "text-sm bg-blue-800 text-white px-3 py-1 rounded-full"
                )
                pending_chip = ui.label("Pending: —").classes(
                    "text-sm bg-yellow-500 text-white px-3 py-1 rounded-full"
                )
                high_chip = ui.label("High Priority: —").classes(
                    "text-sm bg-red-500 text-white px-3 py-1 rounded-full"
                )

            with ui.row().classes("items-center gap-3"):
                ui.label(f"👤 {name}").classes("text-sm text-blue-200")
                ui.button("Logout", on_click=lambda: _logout()).props("flat dense").classes(
                    "text-white"
                )

        # ── Filters ───────────────────────────────────────────────────────────
        with ui.row().classes(
            "w-full items-center gap-3 px-6 py-3 bg-white shadow-sm flex-wrap"
        ):
            ui.label("Filters:").classes("text-sm font-semibold text-gray-600")

            status_select = ui.select(
                options=["All", "PENDING", "ACCEPTED", "REJECTED", "MORE_INFO_REQUESTED"],
                value="All",
                label="Status",
            ).props("outlined dense").classes("w-48")

            priority_select = ui.select(
                options=["All", "HIGH", "MEDIUM", "LOW"],
                value="All",
                label="Priority",
            ).props("outlined dense").classes("w-36")

            sort_select = ui.select(
                options={
                    "created_at_desc": "Newest first",
                    "created_at_asc": "Oldest first",
                    "priority_desc": "Priority (high→low)",
                    "priority_asc": "Priority (low→high)",
                    "username_asc": "Username A→Z",
                },
                value="created_at_desc",
                label="Sort by",
            ).props("outlined dense").classes("w-48")

            ui.button(icon="refresh", on_click=lambda: ui.timer(0.1, _refresh, once=True)).props(
                "flat round dense"
            ).classes("text-[#1a3a6b]").tooltip("Refresh")

        # ── Table container ───────────────────────────────────────────────────
        table_container = ui.column().classes("w-full px-6 py-4")

        # ── Helpers ───────────────────────────────────────────────────────────

        def _logout() -> None:
            app.storage.user.clear()
            ui.navigate.to("/login")

        async def _refresh() -> None:
            """Fetch cases from the API and rebuild the table."""
            sv = status_select.value
            pv = priority_select.value
            sort_val = sort_select.value
            col, direction = sort_val.rsplit("_", 1)

            status_filter = None if sv == "All" else sv
            priority_filter = None if pv == "All" else pv

            try:
                data = await client.get_cases(
                    status=status_filter,
                    priority=priority_filter,
                    sort_by=col,
                    sort_dir=direction,
                    page_size=100,
                )
                cases_data: list[dict] = data.get("items", [])
                total: int = data.get("total", 0)
            except Exception:
                ui.notify("Failed to load cases — check API connection.", type="negative")
                return

            pending = sum(1 for c in cases_data if c["status"] == "PENDING")
            high = sum(
                1 for c in cases_data
                if c["priority"] == "HIGH" and c["status"] == "PENDING"
            )
            total_chip.set_text(f"Total: {total}")
            pending_chip.set_text(f"Pending: {pending}")
            high_chip.set_text(f"High Priority: {high}")

            table_container.clear()
            with table_container:
                if not cases_data:
                    with ui.column().classes("w-full items-center py-16 gap-3"):
                        ui.label("📂").classes("text-5xl")
                        ui.label("No cases found").classes("text-gray-400 text-lg")
                    return

                _render_table(cases_data, client, _refresh)

        # ── Wire up filters and timers ────────────────────────────────────────
        status_select.on_value_change(lambda _: ui.timer(0.1, _refresh, once=True))
        priority_select.on_value_change(lambda _: ui.timer(0.1, _refresh, once=True))
        sort_select.on_value_change(lambda _: ui.timer(0.1, _refresh, once=True))

        ui.timer(30, _refresh)
        ui.timer(0.1, _refresh, once=True)


def _fmt_date(iso: str) -> str:
    """Format an ISO-8601 datetime string for display.

    Args:
        iso: ISO-8601 string from the API.

    Returns:
        Human-readable date string such as ``"24 May 2026 14:30"``.
    """
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y %H:%M")
    except Exception:
        return iso[:16]


def _render_table(
    cases_data: list[dict],
    client: APIClient,
    refresh_fn,
) -> None:
    """Build and display the cases table using NiceGUI's ui.table with Quasar slots.

    Args:
        cases_data: List of case dicts returned by the API.
        client: API client used for action calls and download URL generation.
        refresh_fn: Async callback to reload the table after an action.
    """
    columns = [
        {"name": "id", "label": "ID", "field": "id", "sortable": True, "align": "left"},
        {"name": "username", "label": "Username", "field": "username", "sortable": True},
        {"name": "date", "label": "Date", "field": "date", "sortable": True},
        {"name": "description", "label": "Description", "field": "desc", "align": "left"},
        {"name": "priority", "label": "Priority", "field": "priority", "sortable": True},
        {"name": "status", "label": "Status", "field": "status", "sortable": True},
        {"name": "document", "label": "Document", "field": "document_original_name"},
        {"name": "actions", "label": "Actions", "field": "status"},
    ]

    rows = []
    for case in cases_data:
        desc = case.get("description", "")
        rows.append({
            **case,
            "date": _fmt_date(case.get("created_at", "")),
            "desc": desc[:110] + "…" if len(desc) > 110 else desc,
            "download_url": (
                client.document_download_url(case["id"])
                if case.get("document_original_name")
                else ""
            ),
        })

    table = ui.table(columns=columns, rows=rows, row_key="id").classes(
        "w-full rounded-xl shadow-sm"
    ).props("flat bordered")

    table.add_slot(
        "header",
        """
        <q-tr :props="props">
          <q-th v-for="col in props.cols" :key="col.name" :props="props"
                style="background:#1a3a6b; color:white; font-weight:600; font-size:13px;">
            {{ col.label }}
          </q-th>
        </q-tr>
        """,
    )

    table.add_slot(
        "body",
        """
        <q-tr :props="props"
              :style="props.row.priority === 'HIGH' && props.row.status === 'PENDING'
                        ? 'background:#fff5f5' : ''">

          <q-td key="id" :props="props">
            <span style="font-family:monospace; color:#6b7280;">#{{ props.row.id }}</span>
          </q-td>

          <q-td key="username" :props="props">
            <strong>{{ props.row.username }}</strong>
          </q-td>

          <q-td key="date" :props="props" style="white-space:nowrap; color:#6b7280;">
            {{ props.row.date }}
          </q-td>

          <q-td key="description" :props="props" style="max-width:280px;">
            <span :title="props.row.description" style="color:#374151; line-height:1.4;">
              {{ props.row.desc }}
            </span>
          </q-td>

          <q-td key="priority" :props="props">
            <q-badge
              :color="props.row.priority === 'HIGH' ? 'red-8'
                     : props.row.priority === 'MEDIUM' ? 'orange-8' : 'green-8'"
              style="font-size:12px; padding:3px 8px;">
              {{ props.row.priority === 'HIGH' ? '🔴'
                 : props.row.priority === 'MEDIUM' ? '🟡' : '🟢' }}
              {{ props.row.priority }}
            </q-badge>
          </q-td>

          <q-td key="status" :props="props">
            <q-badge
              :color="props.row.status === 'PENDING' ? 'blue-7'
                     : props.row.status === 'ACCEPTED' ? 'green-7'
                     : props.row.status === 'REJECTED' ? 'red-7' : 'purple-7'"
              style="font-size:12px; padding:3px 8px;">
              {{ props.row.status.replace(/_/g, ' ') }}
            </q-badge>
          </q-td>

          <q-td key="document" :props="props">
            <a v-if="props.row.document_original_name"
               :href="props.row.download_url" target="_blank"
               style="color:#1a3a6b; text-decoration:underline; font-size:12px;">
              📎 {{ props.row.document_original_name }}
            </a>
            <span v-else style="color:#9ca3af;">—</span>
          </q-td>

          <q-td key="actions" :props="props">
            <div v-if="props.row.status === 'PENDING'" style="display:flex; gap:4px;">
              <q-btn dense unelevated color="positive" label="✓ Accept" size="xs"
                     @click="$parent.$emit('accept', props.row)" />
              <q-btn dense unelevated color="negative" label="✗ Reject" size="xs"
                     @click="$parent.$emit('reject', props.row)" />
              <q-btn dense unelevated color="warning" text-color="white" label="? Info" size="xs"
                     @click="$parent.$emit('req_info', props.row)" />
            </div>
            <span v-else style="color:#9ca3af; font-size:12px; font-style:italic;">
              {{ (props.row.lawyer_note || '—').substring(0, 45) }}
            </span>
          </q-td>

        </q-tr>
        """,
    )

    table.on("accept", lambda e: _show_accept_dialog(e.args, client, refresh_fn))
    table.on("reject", lambda e: _show_reject_dialog(e.args, client, refresh_fn))
    table.on("req_info", lambda e: _show_info_dialog(e.args, client, refresh_fn))


def _show_accept_dialog(case: dict, client: APIClient, refresh_fn) -> None:
    """Open the accept-case confirmation dialog.

    Args:
        case: Case dict from the table row.
        client: API client instance.
        refresh_fn: Async callback to refresh the table after success.
    """
    with ui.dialog() as dlg, ui.card().classes("w-96 p-6 gap-4"):
        ui.label(f"Accept Case #{case['id']}").classes("text-lg font-bold text-[#1a3a6b]")
        ui.label(
            f"Client: {case['username']}  •  Priority: {case['priority']}"
        ).classes("text-sm text-gray-500")
        note_input = ui.textarea(
            label="Optional note to client",
            placeholder="e.g. Our team will be in touch within 48 hours.",
        ).props("outlined dense").classes("w-full")

        async def confirm() -> None:
            try:
                await client.accept_case(case["id"], note_input.value or None)
                ui.notify(f"Case #{case['id']} accepted.", type="positive")
                dlg.close()
                await refresh_fn()
            except Exception:
                ui.notify("Failed to accept case.", type="negative")

        with ui.row().classes("justify-end gap-2"):
            ui.button("Cancel", on_click=dlg.close).props("flat")
            ui.button("Accept", on_click=confirm).props("unelevated").classes(
                "bg-green-600 text-white"
            )
    dlg.open()


def _show_reject_dialog(case: dict, client: APIClient, refresh_fn) -> None:
    """Open the reject-case dialog with a mandatory reason field.

    Args:
        case: Case dict from the table row.
        client: API client instance.
        refresh_fn: Async callback to refresh the table after success.
    """
    with ui.dialog() as dlg, ui.card().classes("w-96 p-6 gap-4"):
        ui.label(f"Reject Case #{case['id']}").classes("text-lg font-bold text-red-700")
        ui.label(
            f"Client: {case['username']}  •  Priority: {case['priority']}"
        ).classes("text-sm text-gray-500")
        reason_input = ui.textarea(
            label="Rejection reason (required — sent to client)",
            placeholder="e.g. This matter falls outside our areas of practice.",
        ).props("outlined dense").classes("w-full")

        async def confirm() -> None:
            if not reason_input.value.strip():
                ui.notify("A reason is required.", type="warning")
                return
            try:
                await client.reject_case(case["id"], reason_input.value.strip())
                ui.notify(f"Case #{case['id']} rejected.", type="warning")
                dlg.close()
                await refresh_fn()
            except Exception:
                ui.notify("Failed to reject case.", type="negative")

        with ui.row().classes("justify-end gap-2"):
            ui.button("Cancel", on_click=dlg.close).props("flat")
            ui.button("Reject", on_click=confirm).props("unelevated").classes(
                "bg-red-600 text-white"
            )
    dlg.open()


def _show_info_dialog(case: dict, client: APIClient, refresh_fn) -> None:
    """Open the request-more-information dialog.

    Args:
        case: Case dict from the table row.
        client: API client instance.
        refresh_fn: Async callback to refresh the table after success.
    """
    with ui.dialog() as dlg, ui.card().classes("w-96 p-6 gap-4"):
        ui.label(f"Request More Info — Case #{case['id']}").classes(
            "text-lg font-bold text-[#1a3a6b]"
        )
        ui.label(
            f"Client: {case['username']}  •  Priority: {case['priority']}"
        ).classes("text-sm text-gray-500")
        msg_input = ui.textarea(
            label="Message to client (required)",
            placeholder="e.g. Could you please provide the date the contract was signed?",
        ).props("outlined dense").classes("w-full")

        async def confirm() -> None:
            if not msg_input.value.strip():
                ui.notify("A message is required.", type="warning")
                return
            try:
                await client.request_more_info(case["id"], msg_input.value.strip())
                ui.notify(f"Message sent for case #{case['id']}.", type="positive")
                dlg.close()
                await refresh_fn()
            except Exception:
                ui.notify("Failed to send message.", type="negative")

        with ui.row().classes("justify-end gap-2"):
            ui.button("Cancel", on_click=dlg.close).props("flat")
            ui.button("Send", on_click=confirm).props("unelevated").classes(
                "bg-[#1a3a6b] text-white"
            )
    dlg.open()
