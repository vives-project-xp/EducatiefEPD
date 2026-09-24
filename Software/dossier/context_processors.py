from django.conf import settings


def platform_settings(request):
    return {"oidc_enabled": settings.OIDC_ENABLED}
