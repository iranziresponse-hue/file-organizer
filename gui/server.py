"""Runs the Django dashboard on a background thread inside the same process
as the tray app, so there is no separate `manage.py runserver` step for the
packaged exe. use_reloader is off on purpose -- the reloader spawns a second
process via subprocess, which has no console to attach to once this is a
windowed exe and just fails silently.
"""

import threading

DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8765


def start_dashboard_server(host=DASHBOARD_HOST, port=DASHBOARD_PORT):
    from django.core.management import call_command

    thread = threading.Thread(
        target=call_command,
        args=("runserver", f"{host}:{port}"),
        kwargs={"use_reloader": False},
        daemon=True,
        name="organizer-dashboard",
    )
    thread.start()
    return thread


def dashboard_url(host=DASHBOARD_HOST, port=DASHBOARD_PORT):
    return f"http://{host}:{port}/"
