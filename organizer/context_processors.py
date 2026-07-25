"""Template context available on every page, regardless of which view
rendered it -- for things every page's shared chrome (base.html) needs,
like whether to show the Admin nav link."""

from .core import owner_access


def owner_console(request):
    return {"owner_console_visible": owner_access.request_allowed(request)}
