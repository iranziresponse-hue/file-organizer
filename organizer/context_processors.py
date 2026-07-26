"""Template context available on every page, regardless of which view
rendered it -- for things every page's shared chrome (base.html) needs,
like whether to show the Admin nav link."""

from .core import owner_access


def owner_console(request):
    return {"owner_console_visible": owner_access.request_allowed(request)}


def app_version(request):
    """Appended as a ?v= cache-buster on every static CSS/JS reference (see
    base.html and the handful of page templates that load their own extra
    script). Without this, a WebView2 session that ever cached an older
    asset keeps serving it indefinitely across "launches" -- the
    single-instance guard (gui/app.py) means clicking the exe again almost
    never actually starts a fresh process, it just restores whatever window
    is already running, so a stale cached copy from an earlier version can
    persist until the user does a full Quit from the tray. Tying the
    version to organizer.__version__ means every real release forces a
    fresh fetch, the same lesson the static marketing site's own
    cache-busting already learned the hard way."""
    from organizer import __version__

    return {"ORCH_STATIC_VERSION": __version__}


def desktop_shell(request):
    """Whether this page is being viewed inside Orch's own desktop window
    (see gui/main_window.py), as opposed to a regular browser tab pointed
    at the same local dashboard -- set once per session by the bootstrap
    view the desktop window's initial load hits (organizer.views.dashboard.
    desktop_shell_enter), so it survives normal in-app navigation without
    every internal link needing to carry a query parameter. Used to show
    the frameless window's own minimize/close titlebar only where a real
    OS titlebar isn't already doing that job."""
    return {"is_desktop_shell": bool(request.session.get("is_desktop_shell"))}
