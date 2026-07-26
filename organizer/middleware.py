from django.http import HttpResponse

from .core import owner_access


class OwnerAdminAccessMiddleware:
    """Keep Django admin behind the same local owner gate as /owner/."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            (request.path_info == "/admin" or request.path_info.startswith("/admin/"))
            and not owner_access.request_allowed(request)
        ):
            return HttpResponse("Not found", status=404)
        return self.get_response(request)
