from typing import Optional

import httpx
from nicegui import app, ui

from dashboard.services.api_client import APIClient

_PRIORITY_COLORS = {
    "HIGH": ("bg-red-100 text-red-800", "🔴"),
    "MEDIUM": ("bg-yellow-100 text-yellow-800", "🟡"),
    "LOW": ("bg-green-100 text-green-800", "🟢"),
}

_STATUS_COLORS = {
    "PENDING": "bg-blue-100 text-blue-800",
    "ACCEPTED": "bg-green-100 text-green-800",
    "REJECTED": "bg-red-100 text-red-800",
    "MORE_INFO_REQUESTED": "bg-purple-100 text-purple-800",
}


def _badge(text: str, css: str) -> None:
    """Render a small pill-shaped badge.

    Args:
        text: Label text inside the badge.
        css: Tailwind CSS classes for background and text colour.
    """
    ui.label(text).classes(
        f"text-xs font-semibold px-2 py-0.5 rounded-full {css}"
    )


def build_cases_page() -> None:
    """Render the main cases dashboard page.

    Displays a header with quick-stats, filter controls, and a sortable table
    of legal cases.  Each pending row has inline action buttons for accepting,
    rejecting, and requesting more information.

    The page auto-refreshes every 30 seconds and can be manually refreshed via
    the toolbar button.
    """
    token = app.storage.user.get("token")
    name = app.storage.user.get("name", "Lawyer")
    client = APIClient(token=token)

    cases_data: list[dict] = []
    stats: dict = {"total": 0, "pending": 0, "high": 0}

    filter_status: Optional[str] = None
    filter_priority: Optional[str] = None
    sort_by_state = {"col": "created_at", "dir": "desc"}

    ui.query("body").style("background: #f0f4f8")

    with ui.column().classes("w-full min-h-screen"):
        with ui.row().classes(
            "w-full items-center justify-between px-6 py-3 bg-[#1a3a6b] shadow-md"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.label("⚖️").classes("text-2xl")
                ui.label("LegalAI").classes(
                    "text-xl font-bold text-white tracking-wide"
                )

            with ui.row().classes("items-center gap-4"):
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
                ui.button(
                    "Logout",
                    on_click=lambda: _do_logout(),
                ).props("flat dense").classes("text-white")

        with ui.row().classes(
            "w-full items-center gap-3 px-6 py-3 bg-white shadow-sm"
        ):
            ui.label("Filters:").classes("text-sm font-semibold text-gray-600")

            status_select = ui.select(
                options=["All", "PENDING", "ACCEPTED", "REJECTED", "MORE_INFO_REQUESTED"],
                value="All",
                label="Status",
            ).props("outlined dense").classes("w-44")

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

            ui.button(
                icon="refresh",
                on_click=lambda: ui.timer(0.1, lambda: _refresh(), once=True),
            ).props("flat round dense").classes("text-[#1a3a6b]").tooltip("Refresh")

        table_container = ui.column().classes("w-full px-6 py-4 gap-3")

        async def _refresh() -> None:
            """Fetch cases from the API and rebuild the table rows."""
            nonlocal filter_status, filter_priority, cases_data

            sv = status_select.value
            pv = priority_select.value
            sort_val = sort_select.value
            col, direction = sort_val.rsplit("_", 1)

            filter_status = None if sv == "All" else sv
            filter_priority = None if pv == "All" else pv

            try:
                data = await client.get_cases(
                    status=filter_status,
                    priority=filter_priority,
                    sort_by=col,
                    sort_dir=direction,
                    page_size=100,
                )
                cases_data = data.get("items", [])
                total = data.get("total", 0)
            except Exception:
                ui.notify("Failed to load cases — check API connection.", type="negative")
                return

            pending = sum(1 for c in cases_data if c["status"] == "PENDING")
            high = sum(1 for c in cases_data if c["priority"] == "HIGH" and c["status"] == "PENDING")

            total_chip.set_text(f"Total: {total}")
            pending_chip.set_text(f"Pending: {pending}")
            high_chip.set_text(f"High Priority: {high}")

            table_container.clear()
            with table_container:
                if not cases_data:
                    with ui.column().classes("w-full items-center py-16 gap-3"):
                        ui.label("📂").classes("text-5xl")
                        ui.label("No cases found").classes(
                            "text-gray-400 text-lg"
                        )
                    return

                with ui.element("div").classes(
                    "w-full overflow-x-auto rounded-xl shadow-sm bg-white"
                ):
                    with ui.element("table").classes(
                        "w-full text-sm text-left border-collapse"
                    ):
                        with ui.element("thead").classes("bg-[#1a3a6b] text-white"):
                            with ui.element("tr"):
                                for header in [
                                    "ID", "Username", "Date", "Description",
                                    "Priority", "Status", "Document", "Actions"
                                ]:
                                    ui.element("th").classes(
                                        "px-4 py-3 font-semibold text-sm"
                                    ).set_content(header)

                        with ui.element("tbody"):
                            for case in cases_data:
                                _render_case_row(case, client, _refresh)

        def _render_case_row(case: dict, client: APIClient, refresh_fn) -> None:
            """Render a single case as a table row.

            Args:
                case: Case dict from the API response.
                client: API client instance for action calls.
                refresh_fn: Coroutine to call after a successful action.
            """
            is_pending = case["status"] == "PENDING"
            row_cls = "border-b hover:bg-gray-50 transition-colors"
            if case["priority"] == "HIGH" and is_pending:
                row_cls += " bg-red-50"

            with ui.element("tr").classes(row_cls):
                ui.element("td").classes("px-4 py-3 font-mono text-gray-500").set_content(
                    f"#{case['id']}"
                )
                ui.element("td").classes("px-4 py-3 font-semibold").set_content(
                    case["username"]
                )

                from datetime import datetime
                raw_dt = case.get("created_at", "")
                try:
                    dt = datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
                    date_str = dt.strftime("%d %b %Y %H:%M")
                except Exception:
                    date_str = raw_dt[:16]
                ui.element("td").classes("px-4 py-3 text-gray-500 whitespace-nowrap").set_content(
                    date_str
                )

                desc = case.get("description", "")
                short_desc = desc[:120] + "…" if len(desc) > 120 else desc
                with ui.element("td").classes("px-4 py-3 max-w-xs"):
                    ui.label(short_desc).classes("text-gray-700 leading-snug").tooltip(desc)

                p = case["priority"]
                p_css, p_emoji = _PRIORITY_COLORS.get(p, ("bg-gray-100 text-gray-700", "⚪"))
                with ui.element("td").classes("px-4 py-3"):
                    _badge(f"{p_emoji} {p}", p_css)

                s = case["status"].replace("_", " ")
                s_css = _STATUS_COLORS.get(case["status"], "bg-gray-100 text-gray-700")
                with ui.element("td").classes("px-4 py-3"):
                    _badge(s, s_css)

                with ui.element("td").classes("px-4 py-3"):
                    if case.get("document_original_name"):
                        ui.link(
                            "📎 " + (case["document_original_name"] or "file"),
                            client.document_download_url(case["id"]),
                            new_tab=True,
                        ).classes("text-[#1a3a6b] underline text-xs")
                    else:
                        ui.label("—").classes("text-gray-400")

                with ui.element("td").classes("px-4 py-3"):
                    if is_pending:
                        with ui.row().classes("gap-1 flex-nowrap"):
                            ui.button(
                                "✓ Accept",
                                on_click=lambda c=case: _show_accept_dialog(c, client, refresh_fn),
                            ).props("dense unelevated").classes(
                                "bg-green-600 text-white text-xs px-2 py-1 rounded"
                            )
                            ui.button(
                                "✗ Reject",
                                on_click=lambda c=case: _show_reject_dialog(c, client, refresh_fn),
                            ).props("dense unelevated").classes(
                                "bg-red-600 text-white text-xs px-2 py-1 rounded"
                            )
                            ui.button(
                                "? Info",
                                on_click=lambda c=case: _show_info_dialog(c, client, refresh_fn),
                            ).props("dense unelevated").classes(
                                "bg-yellow-500 text-white text-xs px-2 py-1 rounded"
                            )
                    else:
                        note = case.get("lawyer_note") or "—"
                        if len(note) > 40:
                            note = note[:40] + "…"
                        ui.label(note).classes("text-gray-400 text-xs italic")

        def _show_accept_dialog(case: dict, client: APIClient, refresh_fn) -> None:
            """Open the accept-case confirmation dialog.

            Args:
                case: The case dict to accept.
                client: API client instance.
                refresh_fn: Async callback to refresh the table after success.
            """
            with ui.dialog() as dlg, ui.card().classes("w-96 p-6 gap-4"):
                ui.label(f"Accept Case #{case['id']}").classes(
                    "text-lg font-bold text-[#1a3a6b]"
                )
                ui.label(
                    f"Client: {case['username']}  •  Priority: {case['priority']}"
                ).classes("text-sm text-gray-500")
                note_input = ui.textarea(
                    label="Optional note to client",
                    placeholder="e.g. Our team will be in touch within 48 hours.",
                ).props("outlined dense").classes("w-full")

                async def confirm_accept() -> None:
                    """Call the accept endpoint and refresh the table."""
                    try:
                        await client.accept_case(case["id"], note_input.value or None)
                        ui.notify(f"Case #{case['id']} accepted.", type="positive")
                        dlg.close()
                        await refresh_fn()
                    except Exception:
                        ui.notify("Failed to accept case.", type="negative")

                with ui.row().classes("justify-end gap-2"):
                    ui.button("Cancel", on_click=dlg.close).props("flat")
                    ui.button("Accept", on_click=confirm_accept).props(
                        "unelevated"
                    ).classes("bg-green-600 text-white")
            dlg.open()

        def _show_reject_dialog(case: dict, client: APIClient, refresh_fn) -> None:
            """Open the reject-case dialog with a mandatory reason field.

            Args:
                case: The case dict to reject.
                client: API client instance.
                refresh_fn: Async callback to refresh the table after success.
            """
            with ui.dialog() as dlg, ui.card().classes("w-96 p-6 gap-4"):
                ui.label(f"Reject Case #{case['id']}").classes(
                    "text-lg font-bold text-red-700"
                )
                ui.label(
                    f"Client: {case['username']}  •  Priority: {case['priority']}"
                ).classes("text-sm text-gray-500")
                reason_input = ui.textarea(
                    label="Rejection reason (required — sent to client)",
                    placeholder="e.g. This matter falls outside our areas of practice.",
                ).props("outlined dense").classes("w-full")

                async def confirm_reject() -> None:
                    """Validate reason and call the reject endpoint."""
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
                    ui.button("Reject", on_click=confirm_reject).props(
                        "unelevated"
                    ).classes("bg-red-600 text-white")
            dlg.open()

        def _show_info_dialog(case: dict, client: APIClient, refresh_fn) -> None:
            """Open the request-more-information dialog.

            Args:
                case: The case dict to update.
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

                async def confirm_info() -> None:
                    """Validate the message and call the request-info endpoint."""
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
                    ui.button("Send", on_click=confirm_info).props(
                        "unelevated"
                    ).classes("bg-[#1a3a6b] text-white")
            dlg.open()

        def _do_logout() -> None:
            """Clear the session token and redirect to login."""
            app.storage.user.clear()
            ui.navigate.to("/login")

        status_select.on_value_change(lambda _: ui.timer(0.1, lambda: _refresh(), once=True))
        priority_select.on_value_change(lambda _: ui.timer(0.1, lambda: _refresh(), once=True))
        sort_select.on_value_change(lambda _: ui.timer(0.1, lambda: _refresh(), once=True))

        ui.timer(30, lambda: _refresh())
        ui.timer(0.1, lambda: _refresh(), once=True)
