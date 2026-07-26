"""Runs the Django dashboard on a background thread inside the same process
as the tray app, so there is no separate `manage.py runserver` step for the
packaged exe.

This calls Django's internal WSGI plumbing directly (the same handler
`manage.py runserver` ends up using) instead of going through the
`runserver` management command itself. `runserver` reruns the full system
check framework and a pending-migrations check on every launch -- both
already-redundant with the explicit migrate call in gui/app.py -- plus
argument parsing and banner printing. On a real machine that overhead
measured close to half of this thread's total time to first response, and
it's pure startup latency the user sits through on every launch, not a
one-time cost.
"""

import os
import threading

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.servers.basehttp import run as run_wsgi_server
from django.core.servers.basehttp import get_internal_wsgi_application

DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8765


def start_dashboard_server(host=DASHBOARD_HOST, port=DASHBOARD_PORT):
    # Deliberately not in organizer.apps.OrganizerConfig.ready(): ready()
    # fires for every management command, including `manage.py test` --
    # and it fires before the test runner switches to the test database,
    # so a DB write there would land on the real db.sqlite3, not a test
    # fixture. This is the one place that's guaranteed to only run when
    # the real app is actually starting up.
    from organizer.core import jobs
    jobs.mark_stale_tasks_as_interrupted()

    def _serve():
        # StaticFilesHandler wrapping the plain WSGI app is exactly what
        # `runserver --insecure` does under the hood (see Django's
        # contrib.staticfiles runserver override) -- Orch has no separate
        # web server in front of it, so this is still how static assets
        # get served, in dev and in the packaged exe.
        handler = StaticFilesHandler(get_internal_wsgi_application())
        try:
            run_wsgi_server(host, port, handler, threading=True)
        except OSError:
            # Most likely a second Orch instance already bound this port
            # (e.g. the exe was launched twice). This is a daemon thread,
            # so a silent crash here would otherwise leave the tray icon
            # and window running against a dead server forever -- os._exit
            # matches runserver's own handling of the same error, and is
            # required (not sys.exit) because sys.exit doesn't work from a
            # thread other than the main one.
            os._exit(1)

    thread = threading.Thread(target=_serve, daemon=True, name="organizer-dashboard")
    thread.start()
    return thread


def dashboard_url(host=DASHBOARD_HOST, port=DASHBOARD_PORT):
    return f"http://{host}:{port}/"
