# Dashboard — Technical Reference

## Overview

The dashboard is a NiceGUI application that runs as a standalone Python process (`dashboard/`). It has no database of its own — all data is fetched from and written to the FastAPI service via HTTP. NiceGUI renders the UI server-side and pushes DOM updates to the browser over a WebSocket connection, so the Python code directly manipulates UI elements without a JavaScript layer.

```
Browser
  │  WebSocket + HTTP
  ▼
┌──────────────────────────────────────────┐
│  NiceGUI server (dashboard/)             │
│  ┌────────────────────────────────────┐  │
│  │  main.py  (page routing)           │  │
│  │    /login  →  pages/login.py       │  │
│  │    /       →  pages/cases.py       │  │
│  └────────────────────────────────────┘  │
│  services/api_client.py  (httpx)         │
└──────────────────────────────────────────┘
         │  HTTP REST
         ▼
   FastAPI API service
```

---

## Authentication

### Session storage

NiceGUI provides `app.storage.user`, a per-browser-tab dictionary backed by a signed cookie (the cookie is signed using `NICEGUI_SECRET_KEY`). The dashboard stores two values after a successful login:

| Key | Value |
|---|---|
| `token` | JWT access token returned by `POST /auth/login` |
| `name` | Display name of the authenticated user |

### Route guard

Both pages check `app.storage.user.get("token")` at the top of their page function. If the token is absent the browser is redirected to `/login` (or to `/` from the login page if already authenticated). There is no middleware — the guard is inline in each page function.

```python
@ui.page("/")
def cases_page() -> None:
    if not app.storage.user.get("token"):
        ui.navigate.to("/login")
        return
    build_cases_page()
```

The JWT is not validated client-side. If the token is expired, the first API call will return `401`, which surfaces as a NiceGUI notification. The user must log in again.

### API authentication

All API calls include the JWT in a `?token=` query parameter rather than an `Authorization` header. This is a deliberate simplification for the NiceGUI context: NiceGUI's `ui.link` and direct-download URLs need authentication embedded in the URL itself, and query-parameter auth makes those consistent with programmatic calls from `APIClient`.

---

## Page structure

### `main.py`

Registers two pages using `@ui.page` decorators and calls `ui.run()` with the settings from `config.py`. The `__name__ in {"__main__", "__mp_main__"}` guard ensures the server starts correctly both when run directly and when NiceGUI forks the process for its internal multi-process model.

### `pages/login.py` — `build_login_page()`

Renders a single centred card. Layout:

```
┌─────────────────────────┐
│  [navy header]           │
│  ⚖️  LegalAI             │
│  Case Management Portal  │
├─────────────────────────┤
│  Email field             │
│  Password field          │
│  Error label (hidden)    │
│  [ Sign In ]             │
└─────────────────────────┘
```

The `attempt_login` coroutine is bound to both the button click and the Enter key on the password field. On success it writes to `app.storage.user` and navigates to `/`. On failure the error label becomes visible with a message.

### `pages/cases.py` — `build_cases_page()`

Renders the full case management interface. The layout is divided into three horizontal bands:

```
┌─────────────────────────────────────────────────────────┐
│  HEADER  ⚖️ LegalAI   [Total] [Pending] [High]  [Logout] │
├─────────────────────────────────────────────────────────┤
│  FILTERS  Status ▼   Priority ▼   Sort by ▼   [⟳]       │
├─────────────────────────────────────────────────────────┤
│  TABLE                                                  │
│  ID │ Username │ Date │ Description │ Priority │ Status │
│     │ Document │ Actions                                 │
│  ── │ ──────── │ ──── │ ─────────── │ ──────── │ ────── │
│  #1 │ john_doe │ ...  │ ...         │ 🔴 HIGH  │ PENDING│
│     │ 📎 file  │ [✓ Accept] [✗ Reject] [? Info]         │
└─────────────────────────────────────────────────────────┘
```

---

## Data flow

### Initial load and refresh

`_refresh()` is an async coroutine defined inside `build_cases_page`. It:

1. Reads the current values of the three filter/sort selectors.
2. Calls `APIClient.get_cases()` with the resolved parameters.
3. Clears `table_container` and rebuilds all rows from the API response.
4. Updates the header stat chips.

It is triggered in three ways:
- `ui.timer(0.1, ..., once=True)` on page load (near-immediate first fetch).
- `ui.timer(30, ...)` for automatic 30-second polling.
- `on_value_change` handlers on each filter/sort selector.

Because NiceGUI's UI operations are not thread-safe, `_refresh` must be called as an async coroutine from within the NiceGUI event loop. The pattern `ui.timer(0.1, lambda: _refresh(), once=True)` schedules it on the next event loop tick, which is the correct way to trigger async work from a synchronous event handler.

### Row rendering

`_render_case_row(case, client, refresh_fn)` is called once per case dict. It builds a `<tr>` element with NiceGUI's `ui.element("tr")` and populates each `<td>` inline. Key decisions:

- Descriptions longer than 120 characters are truncated with an ellipsis; the full text is shown in a Quasar tooltip on hover.
- The date is parsed from ISO-8601 and reformatted to `dd Mon YYYY HH:MM`.
- Priority and status are rendered as pill badges using `_badge()`, a helper that applies Tailwind colour classes.
- High-priority pending rows receive a `bg-red-50` background to draw the lawyer's attention.
- Action buttons are only rendered when `status == "PENDING"`. For resolved cases, the `lawyer_note` is shown in truncated italic text instead.

---

## Action dialogs

Each action opens a `ui.dialog` containing a `ui.card`. The dialog is created inside a closure that captures the specific `case` dict, the `client` instance, and the `refresh_fn` callback. This avoids a shared mutable state problem that would arise from a single reused dialog.

### Accept

Opens a dialog with an optional note textarea. On confirm:
1. Calls `APIClient.accept_case(case_id, note)`.
2. Shows a positive notification.
3. Closes the dialog.
4. Awaits `refresh_fn()` to reload the table.

### Reject

Same structure as Accept but the reason textarea is mandatory. The `confirm_reject` coroutine validates that the field is non-empty before calling the API.

### Request more info

Same structure as Reject. The message is mandatory. On success the case status changes to `MORE_INFO_REQUESTED` in the API, and the message is forwarded to the client via the bot.

---

## API client (`services/api_client.py`)

`APIClient` wraps `httpx.AsyncClient` with the API base URL and the JWT token. Each method creates a new client instance per call rather than maintaining a persistent connection. This is intentional for a low-volume dashboard: it avoids connection-lifetime management complexity and keeps each call independently cancellable.

The one exception to programmatic API calls is the document download. `document_download_url(case_id)` returns a plain URL string (with the token embedded as a query parameter) that is passed to `ui.link` with `new_tab=True`. The browser opens the URL directly, triggering the FastAPI `FileResponse` stream.

---

## Styling approach

The dashboard uses Tailwind CSS utility classes applied through NiceGUI's `.classes()` method. No custom CSS file is required. The colour palette is:

| Role | Value |
|---|---|
| Primary (navy) | `#1a3a6b` |
| HIGH priority | red-100 / red-800 |
| MEDIUM priority | yellow-100 / yellow-800 |
| LOW priority | green-100 / green-800 |
| PENDING status | blue-100 / blue-800 |
| ACCEPTED status | green-100 / green-800 |
| REJECTED status | red-100 / red-800 |
| MORE_INFO status | purple-100 / purple-800 |

NiceGUI uses Quasar under the hood, so Quasar props (e.g. `outlined`, `dense`, `unelevated`, `flat`, `round`) can be passed via `.props()` to any component that maps to a Quasar element.

---

## Configuration

`dashboard/src/dashboard/config.py` uses `pydantic-settings` to load from environment variables (and `.env` if present). The only settings the dashboard needs are:

| Setting | Default |
|---|---|
| `API_URL` | `http://localhost:8000` |
| `NICEGUI_SECRET_KEY` | `change-me-nicegui-secret` |
| `HOST` | `0.0.0.0` |
| `PORT` | `8080` |

In the Docker Compose setup, `API_URL` is overridden to `http://api:8000` so the dashboard container reaches the API container by service name rather than `localhost`.
