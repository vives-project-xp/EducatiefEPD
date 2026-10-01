"""Provision disposable local OIDC fixtures in the pinned Authentik test instance.

Run with: docker compose exec -T server ak shell -c
"exec(open('/epd-bootstrap/bootstrap.py').read())"
"""

import os

from django.db import transaction

from authentik.core.models import Application, Group, User
from authentik.crypto.models import CertificateKeyPair
from authentik.flows.models import Flow
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping


def required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing {name} in authentik/.env")
    return value


@transaction.atomic
def provision():
    admin = User.objects.get(username="akadmin")
    if not admin.has_usable_password():
        admin.set_password(required("EPD_TEST_ADMIN_PASSWORD"))
        admin.save(update_fields=["password"])

    fixtures = (
        ("epd-student", "EPD Teststudent", "epd-studenten", "EPD_TEST_STUDENT_PASSWORD"),
        ("epd-docent", "EPD Testdocent", "epd-docenten", "EPD_TEST_TEACHER_PASSWORD"),
        ("epd-beheerder", "EPD Testbeheerder", "epd-beheerders", "EPD_TEST_MANAGER_PASSWORD"),
    )
    for username, name, group_name, password_name in fixtures:
        group, _ = Group.objects.get_or_create(name=group_name)
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"name": name, "email": f"{username}@example.invalid"},
        )
        if created:
            user.set_password(required(password_name))
            user.save(update_fields=["password"])
        user.groups.add(group)

    for slug, client_id, secret_name, title in (
        ("educatief-epd", "educatief-epd-local", "EPD_OIDC_CLIENT_SECRET", "Educatief EPD lokaal"),
        (
            "educatief-epd-alt", "educatief-epd-alt-local",
            "EPD_OIDC_SECOND_CLIENT_SECRET", "Educatief EPD tweede provider",
        ),
    ):
        provider, _ = OAuth2Provider.objects.update_or_create(
            name=title,
            defaults={
                "authentication_flow": Flow.objects.get(slug="default-authentication-flow"),
                "authorization_flow": Flow.objects.get(
                    slug="default-provider-authorization-implicit-consent"
                ),
                "invalidation_flow": Flow.objects.get(slug="default-invalidation-flow"),
                "client_type": "confidential",
                "client_id": client_id,
                "client_secret": required(secret_name),
                "grant_types": ["authorization_code"],
                "_redirect_uris": [
                    {
                        "matching_mode": "strict",
                        "url": "http://localhost:8001/oidc/callback/",
                        "redirect_uri_type": "authorization",
                    },
                    {
                        "matching_mode": "strict",
                        "url": "http://localhost:8001/accounts/login/",
                        "redirect_uri_type": "logout",
                    },
                ],
                "signing_key": CertificateKeyPair.objects.get(
                    name="authentik Internal JWT Certificate"
                ),
            },
        )
        provider.property_mappings.set(
            ScopeMapping.objects.filter(scope_name__in=("openid", "profile", "email"))
        )
        Application.objects.update_or_create(
            slug=slug,
            defaults={"name": title, "provider": provider},
        )
    print("Two local EPD OIDC applications and three role accounts are ready.")


provision()
