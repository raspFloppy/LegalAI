from datetime import datetime
from typing import Optional

from nicegui import app, ui

from dashboard import strings
from dashboard.services.api_client import APIClient


def build_cases_page() -> None:
    """Render the main cases dashboard page.

    Displays a header with quick-stats, filter/sort controls, and a sortable
    table of legal cases.  Each pending row has inline action buttons for
    accepting, rejecting, and requesting more information.  The page
    auto-refreshes every 30 seconds.
    """
    token: str = app.storage.user.get("token")
    name: str = app.storage.user.get("name", "Avvocato")
    client = APIClient(token=token)

    ui.query("body").style("background: #f8fafc")

    # ── Header & Navigation ────────────────────────────────────────────────
    with ui.header(elevated=True).classes("bg-white text-slate-900 px-4 md:px-6 py-2 items-center"):
        with ui.row().classes("items-center gap-2 md:gap-4"):
            ui.label("⚖️").classes("text-xl md:text-2xl")
            ui.label("LegalAI").classes("text-lg md:text-xl font-bold tracking-tight text-blue-900")

        with ui.row().classes("items-center gap-2 md:gap-3 ml-auto"):
            with ui.row().classes("items-center gap-1 md:gap-2 mr-2 md:mr-4 hidden sm:flex"):
                total_chip = ui.badge(strings.STATS_TOTAL_PLACEHOLDER, color="blue-1", text_color="blue-9").classes("px-2 md:px-3 py-1 text-xs md:sm font-medium")
                pending_chip = ui.badge(strings.STATS_PENDING_PLACEHOLDER, color="orange-1", text_color="orange-9").classes("px-2 md:px-3 py-1 text-xs md:sm font-medium")
                high_chip = ui.badge(strings.STATS_HIGH_PLACEHOLDER, color="red-1", text_color="red-9").classes("px-2 md:px-3 py-1 text-xs md:sm font-medium")

            ui.separator().props("vertical").classes("mx-1 md:mx-2 hidden md:block")

            with ui.row().classes("items-center gap-2"):
                ui.label(name).classes("text-xs md:sm font-medium text-slate-700 truncate max-w-[80px] md:max-w-none")
                ui.button(icon="logout", on_click=lambda: _logout()).props("flat round dense").classes(
                    "text-slate-500"
                ).tooltip(strings.LOGOUT_TOOLTIP)

    # ── Status Tabs Bar (Below Header) ────────────────────────────────────
    with ui.row().classes("w-full bg-white border-b border-slate-100 px-4 md:px-8 py-0"):
        with ui.tabs().classes("text-blue-800") as status_tabs:
            ui.tab(strings.TAB_ALL_VALUE, label=strings.TAB_ALL_LABEL)
            ui.tab("PENDING", label=strings.TAB_PENDING_LABEL)
            ui.tab("ACCEPTED", label=strings.TAB_ACCEPTED_LABEL)
            ui.tab("REJECTED", label=strings.TAB_REJECTED_LABEL)
            ui.tab("MORE_INFO_REQUESTED", label=strings.TAB_MORE_INFO_LABEL)

    # ── Table ─────────────────────────────────────────────────────────────
    columns = [
        {"name": "id", "label": strings.COL_ID, "field": "id", "sortable": True, "align": "left"},
        {"name": "username", "label": strings.COL_CLIENT, "field": "username", "sortable": True, "align": "left"},
        {"name": "date", "label": strings.COL_DATE, "field": "date", "sortable": True, "align": "left"},
        {"name": "description", "label": strings.COL_DESCRIPTION, "field": "description", "align": "left", "style": "width: 400px; max-width: 400px;"},
        {"name": "priority", "label": strings.COL_PRIORITY, "field": "priority", "sortable": True, "align": "left"},
        {"name": "status", "label": strings.COL_STATUS, "field": "status", "sortable": True, "align": "left"},
        {"name": "document", "label": strings.COL_DOCUMENT, "field": "document_original_name", "align": "left"},
        {"name": "actions", "label": strings.COL_ACTIONS, "field": "id", "align": "left"},
    ]

    table = ui.table(columns=columns, rows=[], row_key="id").classes(
        "w-full bg-white rounded-xl shadow-sm border border-slate-100 mx-4 md:mx-8 my-4"
    ).props("flat")

    with table.add_slot("no-data"):
        with ui.column().classes("w-full items-center py-20 gap-4"):
            ui.icon("folder_open", size="64px").classes("text-slate-200")
            ui.label(strings.NO_CASES).classes("text-slate-400 text-lg font-medium")

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
              {{ props.row.priority_label }}
            </q-chip>
          </q-td>

          <q-td key="status" :props="props">
            <q-badge
              :color="props.row.status === 'PENDING' ? 'blue-6'
                     : props.row.status === 'ACCEPTED' ? 'green-6'
                     : props.row.status === 'REJECTED' ? 'red-6' : 'purple-6'"
              class="px-2 py-1 rounded text-weight-medium">
              {{ props.row.status_label }}
            </q-badge>
          </q-td>

          <q-td key="document" :props="props">
            <div v-if="props.row.download_urls && props.row.download_urls.length" class="column items-start q-gutter-xs">
              <q-btn v-for="(doc, i) in props.row.download_urls" :key="i"
                     :href="doc.url" target="_blank"
                     flat dense color="primary" size="sm" icon="attach_file"
                     :label="doc.name"
                     class="text-lowercase" />
            </div>
            <span v-else class="text-slate-300">—</span>
          </q-td>

          <q-td key="actions" :props="props">
            <div class="row q-gutter-sm no-wrap items-center justify-end">
              <!-- Case Management Actions -->
              <div class="row q-gutter-xs no-wrap items-center">
                <template v-if="props.row.status === 'PENDING'">
                  <q-btn flat dense color="positive" size="sm"
                         @click="$parent.$emit('accept', props.row)" label="Accetta" class="text-weight-bold" />
                  <q-btn flat dense color="negative" size="sm"
                         @click="$parent.$emit('reject', props.row)" label="Rifiuta" class="text-weight-bold" />
                  <q-btn flat dense color="warning" size="sm"
                         @click="$parent.$emit('req_info', props.row)" label="Info" class="text-weight-bold" />
                </template>
                <template v-else>
                  <div class="text-slate-400 text-caption italic truncate" style="max-width: 150px;" :title="props.row.lawyer_note">
                    {{ props.row.lawyer_note || '—' }}
                  </div>
                </template>
              </div>

              <q-separator vertical inset />

              <!-- Administrative Actions -->
              <div class="row no-wrap">
                <q-btn flat round dense color="grey-7" size="sm" icon="edit"
                       @click="$parent.$emit('edit', props.row)" tooltip="Modifica" />
                <q-btn flat round dense color="negative" size="sm" icon="delete"
                       @click="$parent.$emit('delete', props.row)" tooltip="Elimina" />
              </div>
            </div>
          </q-td>

        </q-tr>
        """,
    )

    table.on("show_desc", lambda e: _show_description_dialog(e.args, client, _refresh))
    table.on("accept", lambda e: _show_accept_dialog(e.args, client, _refresh))
    table.on("reject", lambda e: _show_reject_dialog(e.args, client, _refresh))
    table.on("req_info", lambda e: _show_info_dialog(e.args, client, _refresh))
    table.on("edit", lambda e: _show_edit_dialog(e.args, client, _refresh))
    table.on("delete", lambda e: _show_delete_dialog(e.args, client, _refresh))

    # ── Helpers ───────────────────────────────────────────────────────────

    def _logout() -> None:
        app.storage.user.clear()
        ui.navigate.to("/login")

    async def _refresh() -> None:
        """Fetch cases from the API and update the table rows."""
        sv = status_tabs.value
        sort_val = "created_at_desc"
        col, direction = sort_val.rsplit("_", 1)

        status_filter = None if sv == strings.TAB_ALL_VALUE else sv

        try:
            data = await client.get_cases(
                status=status_filter,
                priority=None,
                sort_by=col,
                sort_dir=direction,
                page_size=100,
            )
            cases_data: list[dict] = data.get("items", [])
            total: int = data.get("total", 0)
        except Exception:
            return

        pending = sum(1 for c in cases_data if c["status"] == "PENDING")
        high = sum(
            1 for c in cases_data
            if c["priority"] == "HIGH" and c["status"] == "PENDING"
        )
        total_chip.set_text(strings.STATS_TOTAL.format(n=total))
        pending_chip.set_text(strings.STATS_PENDING.format(n=pending))
        high_chip.set_text(strings.STATS_HIGH.format(n=high))

        new_rows = []
        for case in cases_data:
            docs: list[str] = case.get("documents") or (
                [case["document_original_name"]] if case.get("document_original_name") else []
            )
            new_rows.append({
                **case,
                "date": _fmt_date(case.get("created_at", "")),
                "priority_label": strings.PRIORITY_LABELS.get(case["priority"], case["priority"]),
                "status_label": strings.STATUS_LABELS.get(case["status"], case["status"]),
                "download_urls": [
                    {"name": name, "url": client.document_download_url(case["id"], idx)}
                    for idx, name in enumerate(docs)
                ],
            })

        table.rows = new_rows
        table.update()

    # ── Wire up filters and timers ────────────────────────────────────────
    status_tabs.on_value_change(lambda _: ui.timer(0.1, _refresh, once=True))

    ui.timer(10, _refresh)
    ui.timer(0.1, _refresh, once=True)


def _fmt_date(iso: str) -> str:
    """Format an ISO-8601 datetime string for display.

    Args:
        iso: ISO-8601 string from the API.

    Returns:
        Human-readable date string such as ``"24 mag 2026 14:30"``.
    """
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y %H:%M")
    except Exception:
        return iso[:16]


def _show_description_dialog(case: dict, client: APIClient, refresh_fn) -> None:
    """Open a dialog showing the full case description."""
    with ui.dialog() as dlg, ui.card().classes("w-[500px] p-6 gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(strings.DESC_TITLE.format(id=case["id"])).classes("text-lg font-bold text-slate-800")
            ui.button(icon="close", on_click=dlg.close).props("flat round dense").classes("text-slate-400")

        ui.separator()

        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("gap-2 items-center"):
                ui.badge(
                    strings.PRIORITY_LABELS.get(case["priority"], case["priority"]),
                    color="slate-100",
                    text_color="slate-700",
                )
                ui.label(case["username"]).classes("text-sm font-medium text-slate-500")

            ui.markdown(case["description"]).classes("text-slate-700 leading-relaxed")

        ui.separator().classes("my-2")

        with ui.row().classes("w-full items-center justify-between"):
            if case["status"] == "PENDING":
                with ui.row().classes("gap-4"):
                    ui.button(strings.DESC_BTN_ACCEPT, color="positive",
                              on_click=lambda: (dlg.close(), _show_accept_dialog(case, client, refresh_fn))).props("flat").classes("text-weight-bold")
                    ui.button(strings.DESC_BTN_REJECT, color="negative",
                              on_click=lambda: (dlg.close(), _show_reject_dialog(case, client, refresh_fn))).props("flat").classes("text-weight-bold")
                    ui.button(strings.DESC_BTN_INFO, color="warning",
                              on_click=lambda: (dlg.close(), _show_info_dialog(case, client, refresh_fn))).props("flat").classes("text-weight-bold")
            else:
                ui.label(strings.DESC_STATUS.format(
                    status=strings.STATUS_LABELS.get(case["status"], case["status"])
                )).classes("text-sm italic text-slate-400")

            ui.button(strings.CLOSE_BTN, on_click=dlg.close).props("flat").classes("ml-auto")
    dlg.open()


def _show_accept_dialog(case: dict, client: APIClient, refresh_fn) -> None:
    """Open the accept-case confirmation dialog."""
    with ui.dialog() as dlg, ui.card().classes("w-96 p-6 gap-4"):
        ui.label(strings.ACCEPT_TITLE.format(id=case["id"])).classes("text-lg font-bold text-green-700")
        ui.label(
            strings.ACCEPT_CLIENT_INFO.format(
                username=case["username"],
                priority=strings.PRIORITY_LABELS.get(case["priority"], case["priority"]),
            )
        ).classes("text-sm text-gray-500")
        note_input = ui.textarea(
            label=strings.ACCEPT_NOTE_LABEL,
            placeholder=strings.ACCEPT_NOTE_PLACEHOLDER,
        ).props("outlined dense").classes("w-full")

        async def confirm() -> None:
            try:
                await client.accept_case(case["id"], note_input.value or None)
                ui.notify(strings.ACCEPT_SUCCESS.format(id=case["id"]), type="positive")
                dlg.close()
                await refresh_fn()
            except Exception:
                ui.notify(strings.ACCEPT_ERROR, type="negative")

        with ui.row().classes("justify-end gap-2"):
            ui.button(strings.CANCEL_BTN, on_click=dlg.close).props("flat")
            ui.button(strings.ACCEPT_CONFIRM_BTN, on_click=confirm).props("unelevated").classes(
                "bg-green-600 text-white"
            )
    dlg.open()


def _show_reject_dialog(case: dict, client: APIClient, refresh_fn) -> None:
    """Open the reject-case dialog with a mandatory reason field."""
    with ui.dialog() as dlg, ui.card().classes("w-96 p-6 gap-4"):
        ui.label(strings.REJECT_TITLE.format(id=case["id"])).classes("text-lg font-bold text-red-700")
        ui.label(
            strings.REJECT_CLIENT_INFO.format(
                username=case["username"],
                priority=strings.PRIORITY_LABELS.get(case["priority"], case["priority"]),
            )
        ).classes("text-sm text-gray-500")
        reason_input = ui.textarea(
            label=strings.REJECT_REASON_LABEL,
            placeholder=strings.REJECT_REASON_PLACEHOLDER,
        ).props("outlined dense").classes("w-full")

        async def confirm() -> None:
            if not reason_input.value.strip():
                ui.notify(strings.REJECT_REASON_REQUIRED, type="warning")
                return
            try:
                await client.reject_case(case["id"], reason_input.value.strip())
                ui.notify(strings.REJECT_SUCCESS.format(id=case["id"]), type="warning")
                dlg.close()
                await refresh_fn()
            except Exception:
                ui.notify(strings.REJECT_ERROR, type="negative")

        with ui.row().classes("justify-end gap-2"):
            ui.button(strings.CANCEL_BTN, on_click=dlg.close).props("flat")
            ui.button(strings.REJECT_CONFIRM_BTN, on_click=confirm).props("unelevated").classes(
                "bg-red-600 text-white"
            )
    dlg.open()


def _show_info_dialog(case: dict, client: APIClient, refresh_fn) -> None:
    """Open the request-more-information dialog."""
    with ui.dialog() as dlg, ui.card().classes("w-96 p-6 gap-4"):
        ui.label(strings.INFO_TITLE.format(id=case["id"])).classes(
            "text-lg font-bold text-orange-700"
        )
        ui.label(
            strings.INFO_CLIENT_INFO.format(
                username=case["username"],
                priority=strings.PRIORITY_LABELS.get(case["priority"], case["priority"]),
            )
        ).classes("text-sm text-gray-500")
        msg_input = ui.textarea(
            label=strings.INFO_MSG_LABEL,
            placeholder=strings.INFO_MSG_PLACEHOLDER,
        ).props("outlined dense").classes("w-full")

        async def confirm() -> None:
            if not msg_input.value.strip():
                ui.notify(strings.INFO_MSG_REQUIRED, type="warning")
                return
            try:
                await client.request_more_info(case["id"], msg_input.value.strip())
                ui.notify(strings.INFO_SUCCESS.format(id=case["id"]), type="positive")
                dlg.close()
                await refresh_fn()
            except Exception:
                ui.notify(strings.INFO_ERROR, type="negative")

        with ui.row().classes("justify-end gap-2"):
            ui.button(strings.CANCEL_BTN, on_click=dlg.close).props("flat")
            ui.button(strings.INFO_CONFIRM_BTN, on_click=confirm).props("unelevated").classes(
                "bg-orange-600 text-white"
            )
    dlg.open()


def _show_edit_dialog(case: dict, client: APIClient, refresh_fn) -> None:
    """Open the edit-case dialog for modifying title, description, and priority."""
    with ui.dialog() as dlg, ui.card().classes("w-[480px] p-6 gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(strings.EDIT_TITLE.format(id=case["id"])).classes("text-lg font-bold text-slate-800")
            ui.button(icon="close", on_click=dlg.close).props("flat round dense").classes("text-slate-400")
        
        ui.separator()

        title_input = ui.input(
            label=strings.EDIT_CASE_TITLE_LABEL,
            value=case.get("title", ""),
        ).props("outlined dense").classes("w-full")

        desc_input = ui.textarea(
            label=strings.EDIT_DESCRIPTION_LABEL,
            value=case.get("description", ""),
        ).props("outlined dense").classes("w-full")

        priority_opts = {
            "HIGH": strings.PRIORITY_LABELS["HIGH"],
            "MEDIUM": strings.PRIORITY_LABELS["MEDIUM"],
            "LOW": strings.PRIORITY_LABELS["LOW"],
        }
        priority_select = ui.select(
            options=priority_opts,
            value=case.get("priority", "MEDIUM"),
            label=strings.EDIT_PRIORITY_LABEL,
        ).props("outlined dense").classes("w-full")

        async def confirm() -> None:
            try:
                # Call PATCH API
                await client.patch_case(
                    case["id"],
                    title=title_input.value.strip() or None,
                    description=desc_input.value.strip() or None,
                    priority=priority_select.value,
                )
                ui.notify(strings.EDIT_SUCCESS.format(id=case["id"]), type="positive")
                dlg.close()
                await refresh_fn()
            except Exception as e:
                ui.notify(f"{strings.EDIT_ERROR}: {str(e)}", type="negative")

        with ui.row().classes("justify-end gap-2 mt-2"):
            ui.button(strings.CANCEL_BTN, on_click=dlg.close).props("flat")
            ui.button(strings.EDIT_CONFIRM_BTN, on_click=confirm).props("unelevated").classes(
                "bg-blue-600 text-white"
            )
    dlg.open()


def _show_delete_dialog(case: dict, client: APIClient, refresh_fn) -> None:
    """Open the delete-case confirmation dialog."""
    with ui.dialog() as dlg, ui.card().classes("w-96 p-6 gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(strings.DELETE_TITLE.format(id=case["id"])).classes("text-lg font-bold text-red-700")
            ui.button(icon="close", on_click=dlg.close).props("flat round dense").classes("text-slate-400")
        
        ui.separator()

        ui.html(
            strings.DELETE_CONFIRM_TEXT.format(id=case["id"], username=case["username"])
        ).classes("text-sm text-slate-600 leading-relaxed")

        async def confirm() -> None:
            try:
                await client.delete_case(case["id"])
                ui.notify(strings.DELETE_SUCCESS.format(id=case["id"]), type="positive")
                dlg.close()
                await refresh_fn()
            except Exception as e:
                ui.notify(f"{strings.DELETE_ERROR}: {str(e)}", type="negative")

        with ui.row().classes("justify-end gap-2 mt-2"):
            ui.button(strings.CANCEL_BTN, on_click=dlg.close).props("flat")
            ui.button(strings.DELETE_CONFIRM_BTN, on_click=confirm).props("unelevated").classes(
                "bg-red-600 text-white"
            )
    dlg.open()
