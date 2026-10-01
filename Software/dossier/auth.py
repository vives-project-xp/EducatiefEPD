import hashlib
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.db import transaction
from django.urls import reverse
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from requests.auth import HTTPBasicAuth

from .models import ExternalIdentity, Profile


class EmergencyAdminAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_superuser or user.external_identities.exists():
            raise ValidationError("Deze aanmeldroute is alleen voor de lokale noodbeheerder.")


def oidc_end_session_url(request):
    parameters = {
        "client_id": settings.OIDC_RP_CLIENT_ID,
        "post_logout_redirect_uri": request.build_absolute_uri(reverse("login")),
    }
    id_token = request.session.get("oidc_id_token")
    if id_token:
        parameters["id_token_hint"] = id_token
    return f"{settings.OIDC_END_SESSION_ENDPOINT}?{urlencode(parameters)}"


class EpdOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """Bind a verified OIDC subject to a local EPD account, never an email address."""

    def get_token(self, payload):
        host = settings.OIDC_TOKEN_HOST_HEADER
        if not host:
            return super().get_token(payload)
        if any(character in host for character in "\r\n/\\"):
            raise SuspiciousOperation("Ongeldige OIDC-tokenhost.")
        auth = None
        if self.get_settings("OIDC_TOKEN_USE_BASIC_AUTH", False):
            payload = payload.copy()
            auth = HTTPBasicAuth(payload["client_id"], payload.pop("client_secret"))
        response = requests.post(
            self.OIDC_OP_TOKEN_ENDPOINT,
            data=payload,
            auth=auth,
            headers={"Host": host},
            verify=self.get_settings("OIDC_VERIFY_SSL", True),
            timeout=self.get_settings("OIDC_TIMEOUT", None),
            proxies=self.get_settings("OIDC_PROXY", None),
        )
        self.raise_token_response_error(response)
        return response.json()

    @staticmethod
    def role_from_claims(claims):
        groups = claims.get(settings.OIDC_GROUP_CLAIM)
        if not isinstance(groups, list) or not all(isinstance(group, str) for group in groups):
            raise SuspiciousOperation("OIDC-groepsclaim ontbreekt of is ongeldig.")
        memberships = set(groups)
        if memberships.intersection(settings.OIDC_ADMIN_GROUPS):
            return Profile.Role.ADMIN
        if memberships.intersection(settings.OIDC_TEACHER_GROUPS):
            return Profile.Role.TEACHER
        if memberships.intersection(settings.OIDC_STUDENT_GROUPS):
            return Profile.Role.STUDENT
        raise SuspiciousOperation("Geen EPD-rol toegekend door de identity provider.")

    @transaction.atomic
    def get_or_create_user(self, access_token, id_token, payload):
        issuer = payload.get("iss")
        subject = payload.get("sub")
        if issuer != settings.OIDC_ISSUER or not isinstance(subject, str) or not subject:
            raise SuspiciousOperation("Ongeldige OIDC-issuer of subject.")
        claims = self.get_userinfo(access_token, id_token, payload)
        if not self.verify_claims(claims) or claims.get("sub") != subject:
            raise SuspiciousOperation("OIDC-userinfo komt niet overeen met het ID-token.")
        role = self.role_from_claims(claims)
        identity = ExternalIdentity.objects.select_related("user").filter(
            issuer=issuer, subject=subject
        ).first()
        if identity:
            user = identity.user
            if not user.is_active:
                return None
        else:
            username = "oidc_" + hashlib.sha256(f"{issuer}\0{subject}".encode()).hexdigest()[:40]
            user = get_user_model()(username=username)
            user.set_unusable_password()
        user.email = claims.get("email", "")
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.is_staff = False
        user.is_superuser = False
        user.save()
        if identity is None:
            ExternalIdentity.objects.create(user=user, issuer=issuer, subject=subject)
        Profile.objects.update_or_create(user=user, defaults={"role": role})
        user.refresh_from_db()
        return user
