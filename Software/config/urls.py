from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from dossier import views as dossier_views

urlpatterns = [
    path("accounts/login/", dossier_views.epd_login, name="login"),
    path("accounts/login-fout/", dossier_views.epd_login_failure, name="login_failure"),
    path("accounts/logout/", dossier_views.epd_logout, name="logout"),
    path("accounts/noodlogin/", dossier_views.emergency_login, name="emergency_login"),
    path("", include("dossier.urls")),
]

if settings.OIDC_ENABLED:
    urlpatterns.insert(0, path("oidc/", include("mozilla_django_oidc.urls")))
if settings.EMERGENCY_LOGIN_ENABLED:
    urlpatterns.insert(0, path("admin/", admin.site.urls))
