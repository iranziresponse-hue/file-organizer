"""Template context available on every page, regardless of which view
rendered it -- for things every page's shared chrome (base.html) needs,
like whether to show the Admin nav link."""

from .core import owner_access


def owner_console(request):
    return {"owner_console_visible": owner_access.request_allowed(request)}


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
