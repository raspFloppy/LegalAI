from nicegui import app, ui

from dashboard.services.api_client import APIClient


def build_login_page() -> None:
    """Render the login page UI.

    Displays a centred card with email/password fields.  On successful
    authentication the JWT and user name are stored in ``app.storage.user``
    and the browser is redirected to the cases dashboard.
    """
    ui.query("body").style("background: #f0f4f8")

    with ui.column().classes("absolute-center items-center gap-0"):
        with ui.card().classes(
            "w-96 shadow-lg rounded-2xl overflow-hidden p-0"
        ):
            with ui.column().classes(
                "w-full items-center gap-2 px-10 py-8 bg-[#1a3a6b]"
            ):
                ui.label("⚖️").classes("text-5xl")
                ui.label("LegalAI").classes(
                    "text-2xl font-bold text-white tracking-wide"
                )
                ui.label("Case Management Portal").classes(
                    "text-sm text-blue-200"
                )

            with ui.column().classes("w-full px-10 py-8 gap-4"):
                email_input = ui.input(
                    label="Email address",
                    placeholder="lawyer@firm.com",
                ).props("outlined dense").classes("w-full")

                password_input = ui.input(
                    label="Password",
                    password=True,
                    password_toggle_button=True,
                ).props("outlined dense").classes("w-full")

                error_label = ui.label("").classes(
                    "text-red-600 text-sm hidden"
                )

                async def attempt_login() -> None:
                    """Validate credentials against the API and redirect on success."""
                    error_label.classes(remove="hidden")
                    email = email_input.value.strip()
                    password = password_input.value

                    if not email or not password:
                        error_label.set_text("Please fill in all fields.")
                        return

                    try:
                        client = APIClient()
                        data = await client.login(email, password)
                        app.storage.user["token"] = data["access_token"]
                        app.storage.user["name"] = data["name"]
                        ui.navigate.to("/")
                    except Exception:
                        error_label.set_text("Invalid email or password.")

                login_btn = ui.button("Sign In", on_click=attempt_login).props(
                    "unelevated"
                ).classes(
                    "w-full bg-[#1a3a6b] text-white font-semibold py-2 rounded-lg"
                )

                password_input.on(
                    "keydown.enter", lambda _: login_btn.run_method("click")
                )

        ui.label("LegalAI © 2024").classes("text-xs text-gray-400 mt-4")
