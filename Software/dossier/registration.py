"""Enige plek waar bepaald wordt wie welke registraties ziet en mag wijzigen."""
from django.db.models import Q

from .models import Profile, Registration, StudentCase

R = Registration


def role_of(user):
    if user.is_superuser:
        return Profile.Role.ADMIN
    return getattr(getattr(user, "epd_profile", None), "role", Profile.Role.STUDENT)


def is_staff_role(user):
    return role_of(user) in {Profile.Role.TEACHER, Profile.Role.ADMIN}


def student_is_locked(user, case_id):
    student_case = StudentCase.objects.filter(case_id=case_id, student=user).first()
    return bool(student_case and student_case.locked)


def visible_registrations(user, case):
    """De aanroeper moet de casustoegang al gecontroleerd hebben (editable_case / get_student_case)."""
    queryset = R.objects.filter(case=case).select_related("author", "module")
    if is_staff_role(user):
        return queryset
    return queryset.filter(
        Q(author=user) | Q(author_role=R.AuthorRole.STAFF, status=R.Status.PUBLISHED)
    )


def can_create(user, case):
    return is_staff_role(user) or not student_is_locked(user, case.pk)


def can_edit(user, registration, locked=None):
    """Wijzigen, publiceren en verwijderen: alleen concepten."""
    if registration.status == R.Status.PUBLISHED:
        return False
    if is_staff_role(user):
        return registration.author_id == user.id or registration.author_role == R.AuthorRole.STAFF
    if locked is None:
        locked = student_is_locked(user, registration.case_id)
    return registration.author_id == user.id and not locked


def can_unpublish(user, registration, locked=None):
    if registration.status != R.Status.PUBLISHED:
        return False
    if is_staff_role(user):
        return registration.author_id == user.id or registration.author_role == R.AuthorRole.STAFF
    if locked is None:
        locked = student_is_locked(user, registration.case_id)
    return registration.author_id == user.id and not locked


def annotate_permissions(user, case_id, registrations):
    """Zet can_edit / can_unpublish op elk object, zodat templates er geen argumenten voor nodig hebben."""
    locked = False if is_staff_role(user) else student_is_locked(user, case_id)
    for registration in registrations:
        registration.can_edit = can_edit(user, registration, locked=locked)
        registration.can_unpublish = can_unpublish(user, registration, locked=locked)
    return registrations