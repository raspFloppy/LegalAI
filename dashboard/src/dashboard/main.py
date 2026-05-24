from nicegui import app, ui

from dashboard.config import settings
from dashboard.pages.cases import build_cases_page
from dashboard.pages.login import build_login_page


@ui.page("/login")
def login_page() -> None:
    """Render the login page."""
    if app.storage.user.get("token"):
        ui.navigate.to("/")
        return
    build_login_page()


@ui.page("/")
def cases_page() -> None:
    """Render the cases dashboard.

    Redirects to ``/login`` when no valid session token is found in storage.
    """
    if not app.storage.user.get("token"):
        ui.navigate.to("/login")
        return
    build_cases_page()


def main() -> None:
    """Entry point for running the NiceGUI dashboard server."""
    ui.run(
        host=settings.host,
        port=settings.port,
        title="LegalAI Dashboard",
        favicon="⚖️",
        storage_secret=settings.nicegui_secret_key,
        reload=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
