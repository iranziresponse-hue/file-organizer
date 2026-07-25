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

    # Deliberately not in organizer.apps.OrganizerConfig.ready(): ready()
    # fires for every management command, including `manage.py test` --
    # and it fires before the test runner switches to the test database,
    # so a DB write there would land on the real db.sqlite3, not a test
    # fixture. This is the one place that's guaranteed to only run when
    # the real app is actually starting up.
    from organizer.core import jobs
    jobs.mark_stale_tasks_as_interrupted()

    thread = threading.Thread(
        target=call_command,
        args=("runserver", f"{host}:{port}"),
        # insecure=True keeps runserver's static-file serving on even with
        # DEBUG=False (its default off-switch). Orch has no separate web
        # server in front of it -- runserver serving static assets IS how
        # this app serves static assets, in dev and in the packaged exe.
        kwargs={"use_reloader": False, "insecure": True},
        daemon=True,
        name="organizer-dashboard",
    )
    thread.start()
    return thread


def dashboard_url(host=DASHBOARD_HOST, port=DASHBOARD_PORT):
    return f"http://{host}:{port}/"
