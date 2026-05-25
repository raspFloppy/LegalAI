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

    ui.query("body").style("background: #f8fafc")

    # ── Header & Navigation ────────────────────────────────────────────────
    with ui.header(elevated=True).classes("bg-white text-slate-900 px-4 md:px-6 py-2 items-center"):
        with ui.row().classes("items-center gap-2 md:gap-4"):
            ui.label("⚖️").classes("text-xl md:text-2xl")
            ui.label("LegalAI").classes("text-lg md:text-xl font-bold tracking-tight text-blue-900")

        # Status Tabs - Flexible container
        with ui.tabs().classes("text-blue-800 flex-grow") as status_tabs:
            ui.tab("All")
            ui.tab("PENDING", label="Pending")
            ui.tab("ACCEPTED", label="Accepted")
            ui.tab("REJECTED", label="Rejected")
            ui.tab("MORE_INFO_REQUESTED", label="More Info")

        ui.separator().props("vertical").classes("mx-1 md:mx-2 hidden sm:block")

        with ui.row().classes("items-center gap-2 md:gap-3 ml-auto"):
            # Quick Stats - Hidden on very small screens or wrapped
            with ui.row().classes("items-center gap-1 md:gap-2 mr-2 md:mr-4 hidden sm:flex"):
                total_chip = ui.badge("Total: —", color="blue-1", text_color="blue-9").classes("px-2 md:px-3 py-1 text-xs md:sm font-medium")
                pending_chip = ui.badge("Pending: —", color="orange-1", text_color="orange-9").classes("px-2 md:px-3 py-1 text-xs md:sm font-medium")
                high_chip = ui.badge("High Priority: —", color="red-1", text_color="red-9").classes("px-2 md:px-3 py-1 text-xs md:sm font-medium")

            ui.separator().props("vertical").classes("mx-1 md:mx-2 hidden md:block")

            with ui.row().classes("items-center gap-2"):
                ui.label(name).classes("text-xs md:sm font-medium text-slate-700 truncate max-w-[80px] md:max-w-none")
                ui.button(icon="logout", on_click=lambda: _logout()).props("flat round dense").classes(
                    "text-slate-500"
                ).tooltip("Logout")

    with ui.column().classes("w-full min-h-screen"):
        # ── Table container ───────────────────────────────────────────────────
        table_container = ui.column().classes("w-full px-2 sm:px-4 md:px-8 py-4 md:py-6")

        # ── Helpers ───────────────────────────────────────────────────────────

        def _logout() -> None:
            app.storage.user.clear()
            ui.navigate.to("/login")

        async def _refresh() -> None:
            """Fetch cases from the API and rebuild the table."""
            sv = status_tabs.value
            # Use defaults since selectors were removed
            pv = "All"
            sort_val = "created_at_desc"
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
                    with ui.column().classes("w-full items-center py-20 gap-4"):
                        ui.icon("folder_open", size="64px").classes("text-slate-200")
                        ui.label("No cases found matching these filters").classes("text-slate-400 text-lg font-medium")
                    return

                _render_table(cases_data, client, _refresh)

        # ── Wire up filters and timers ────────────────────────────────────────
        status_tabs.on_value_change(lambda _: ui.timer(0.1, _refresh, once=True))

        ui.timer(10, _refresh)
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
        {"name": "username", "label": "Username", "field": "username", "sortable": True, "align": "left"},
        {"name": "date", "label": "Date", "field": "date", "sortable": True, "align": "left"},
        {"name": "description", "label": "Description", "field": "description", "align": "left", "style": "width: 400px; max-width: 400px;"},
        {"name": "priority", "label": "Priority", "field": "priority", "sortable": True, "align": "left"},
        {"name": "status", "label": "Status", "field": "status", "sortable": True, "align": "left"},
        {"name": "document", "label": "Document", "field": "document_original_name", "align": "left"},
    ]

    rows = []
    for case in cases_data:
        rows.append({
            **case,
            "date": _fmt_date(case.get("created_at", "")),
            "download_url": (
                client.document_download_url(case["id"])
                if case.get("document_original_name")
                else ""
            ),
        })

    table = ui.table(columns=columns, rows=rows, row_key="id").classes(
        "w-full bg-white rounded-xl shadow-sm border border-slate-100"
    ).props("flat")

    table.add_slot(
        "body",
        """
        <q-tr :props="props"
              :class="props.row.priority === 'HIGH' && props.row.status === 'PENDING'
                        ? 'bg-red-50' : 'hover:bg-slate-50 transition-colors'">

          <q-td key="id" :props="props">
            <span class="font-mono text-slate-400">#{{ props.row.id }}</span>
          </q-td>

          <q-td key="username" :props="props">
            <span class="font-semibold text-slate-700">{{ props.row.username }}</span>
          </q-td>

          <q-td key="date" :props="props" class="whitespace-nowrap text-slate-500">
            {{ props.row.date }}
          </q-td>

          <q-td key="description" :props="props" class="cursor-pointer" @click="$parent.$emit('show_desc', props.row)" style="white-space: normal; height: auto;">
            <div :title="props.row.description" class="text-slate-600 line-clamp-3 leading-relaxed break-words" style="width: 400px;">
              {{ props.row.description }}
            </div>
          </q-td>

          <q-td key="priority" :props="props">
            <q-chip
              :color="props.row.priority === 'HIGH' ? 'red-1'
                     : props.row.priority === 'MEDIUM' ? 'orange-1' : 'green-1'"
              :text-color="props.row.priority === 'HIGH' ? 'red-9'
                     : props.row.priority === 'MEDIUM' ? 'orange-9' : 'green-9'"
              size="sm" dense class="font-bold uppercase tracking-wider">
              {{ props.row.priority }}
            </q-chip>
          </q-td>

          <q-td key="status" :props="props">
            <q-badge
              :color="props.row.status === 'PENDING' ? 'blue-6'
                     : props.row.status === 'ACCEPTED' ? 'green-6'
                     : props.row.status === 'REJECTED' ? 'red-6' : 'purple-6'"
              class="px-2 py-1 rounded text-weight-medium">
              {{ props.row.status.replace(/_/g, ' ') }}
            </q-badge>
          </q-td>

          <q-td key="document" :props="props">
            <q-btn v-if="props.row.document_original_name"
                   :href="props.row.download_url" target="_blank"
                   flat dense color="primary" size="sm" icon="attach_file"
                   :label="props.row.document_original_name"
                   class="text-lowercase" />
            <span v-else class="text-slate-300">—</span>
          </q-td>

        </q-tr>
        """,
    )

    table.on("show_desc", lambda e: _show_description_dialog(e.args))
    table.on("accept", lambda e: _show_accept_dialog(e.args, client, refresh_fn))
    table.on("reject", lambda e: _show_reject_dialog(e.args, client, refresh_fn))
    table.on("req_info", lambda e: _show_info_dialog(e.args, client, refresh_fn))


def _show_description_dialog(case: dict) -> None:
    """Open a dialog showing the full case description."""
    with ui.dialog() as dlg, ui.card().classes("w-[500px] p-6 gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"Case #{case['id']} Description").classes("text-lg font-bold text-slate-800")
            ui.button(icon="close", on_click=dlg.close).props("flat round dense").classes("text-slate-400")
        
        ui.separator()
        
        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("gap-2 items-center"):
                ui.badge(case["priority"], color="slate-100", text_color="slate-700")
                ui.label(case["username"]).classes("text-sm font-medium text-slate-500")
            
            ui.markdown(case["description"]).classes("text-slate-700 leading-relaxed")

        with ui.row().classes("w-full justify-end mt-2"):
            ui.button("Close", on_click=dlg.close).props("flat")
    dlg.open()


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
