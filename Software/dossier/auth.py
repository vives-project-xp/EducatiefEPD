from django.conf import settings
from django.contrib.auth import get_user_model
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import Profile


class EpdOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    def filter_users_by_claims(self, claims):
        email = claims.get("email", "")
        return get_user_model().objects.filter(email__iexact=email) if email else get_user_model().objects.none()

    def create_user(self, claims):
        email = claims.get("email", "")
        username = claims.get("preferred_username") or email
        user = get_user_model().objects.create_user(
            username=username,
            email=email,
            first_name=claims.get("given_name", ""),
            last_name=claims.get("family_name", ""),
        )
        self.update_role(user, claims)
        return user

    def update_user(self, user, claims):
        user.email = claims.get("email", user.email)
        user.first_name = claims.get("given_name", user.first_name)
        user.last_name = claims.get("family_name", user.last_name)
        user.save(update_fields=["email", "first_name", "last_name"])
        self.update_role(user, claims)
        return user

    @staticmethod
    def update_role(user, claims):
        groups = set(claims.get("groups", []))
        if groups.intersection(settings.OIDC_ADMIN_GROUPS):
            role = Profile.Role.ADMIN
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        elif groups.intersection(settings.OIDC_TEACHER_GROUPS):
            role = Profile.Role.TEACHER
        else:
            role = Profile.Role.STUDENT
        Profile.objects.update_or_create(user=user, defaults={"role": role})
