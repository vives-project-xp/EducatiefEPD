from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from copy import deepcopy

from .forms import StudentDataForm
from .models import BasisCasus, StudentUitwerking, StudentUitwerkingData, User


def _require_role(user, role):
    if user.role != role:
        raise Http404


@login_required
def dashboard(request):
    if request.user.role == User.Role.DOCENT:
        context = {"casussen": BasisCasus.objects.filter(docent=request.user).select_related("patient")}
    else:
        casussen = list(
            BasisCasus.objects.filter(publicatie_status=BasisCasus.PublicationStatus.OPEN)
            .select_related("patient")
        )
        uitwerkingen = {
            uitwerking.casus_id: uitwerking
            for uitwerking in StudentUitwerking.objects.filter(student=request.user, casus__in=casussen)
        }
        for casus in casussen:
            casus.student_uitwerking = uitwerkingen.get(casus.id)
        context = {
            "casussen": casussen,
            "uitwerkingen": StudentUitwerking.objects.filter(student=request.user).select_related("casus"),
        }
    return render(request, "epd/dashboard.html", context)


def _get_or_create_uitwerking(student, casus):
    uitwerking, created = StudentUitwerking.objects.get_or_create(student=student, casus=casus)
    if created:
        StudentUitwerkingData.objects.bulk_create(
            [
                StudentUitwerkingData(
                    uitwerking=uitwerking,
                    sjabloon_onderdeel_id=casus_data.sjabloon_onderdeel_id,
                    waarde=deepcopy(casus_data.waarde),
                )
                for casus_data in casus.data.all()
            ]
        )
    return uitwerking, created


@login_required
def casus_overzicht(request, casus_id):
    _require_role(request.user, User.Role.STUDENT)
    casus = get_object_or_404(
        BasisCasus.objects.select_related("patient"),
        pk=casus_id,
        publicatie_status=BasisCasus.PublicationStatus.OPEN,
    )
    uitwerking = StudentUitwerking.objects.filter(student=request.user, casus=casus).first()
    return render(request, "epd/casus_overzicht.html", {"casus": casus, "uitwerking": uitwerking})


@login_required
@transaction.atomic
def open_dossier(request, casus_id):
    _require_role(request.user, User.Role.STUDENT)
    casus = get_object_or_404(
        BasisCasus.objects.prefetch_related("data"),
        pk=casus_id,
        publicatie_status=BasisCasus.PublicationStatus.OPEN,
    )
    uitwerking, created = _get_or_create_uitwerking(request.user, casus)
    if created:
        messages.success(request, "De casus is gestart en de startsituatie is gekloond.")
    return redirect("uitwerking", uitwerking_id=uitwerking.id)


@login_required
def start_casus(request, casus_id):
    return open_dossier(request, casus_id)


@login_required
@transaction.atomic
def uitwerking(request, uitwerking_id):
    uitwerking = StudentUitwerking.objects.filter(
        pk=uitwerking_id, student=request.user
    ).select_related("casus__patient").prefetch_related("casus__data", "data").first()
    if uitwerking is None:
        raise Http404
    if not uitwerking.data.exists():
        _get_or_create_uitwerking(request.user, uitwerking.casus)
        uitwerking = StudentUitwerking.objects.select_related("casus__patient").prefetch_related("data").get(pk=uitwerking.id)
    readonly = uitwerking.status != StudentUitwerking.Status.GESTART
    forms = []
    if request.method == "POST" and not readonly:
        for data in uitwerking.data.all():
            form = StudentDataForm(request.POST, instance=data, prefix=f"data-{data.id}")
            if form.is_valid():
                form.save()
            forms.append((data, form))
        if all(form.is_valid() for _, form in forms):
            messages.success(request, "De dossiergegevens zijn opgeslagen.")
            return redirect("uitwerking", uitwerking_id=uitwerking.id)
    else:
        forms = [(data, StudentDataForm(instance=data, prefix=f"data-{data.id}")) for data in uitwerking.data.all()]
    return render(request, "epd/dossier_werkruimte.html", {
        "uitwerking": uitwerking,
        "forms": forms,
        "readonly": readonly,
        "deadline_verstreken": timezone.now() > uitwerking.casus.inlever_deadline,
        "patient": uitwerking.casus.patient,
    })


@login_required
@transaction.atomic
def submit_uitwerking(request, uitwerking_id):
    if request.method != "POST":
        return redirect("uitwerking", uitwerking_id=uitwerking_id)
    uitwerking = get_object_or_404(StudentUitwerking, pk=uitwerking_id, student=request.user)
    if uitwerking.status != StudentUitwerking.Status.GESTART:
        messages.error(request, "Deze uitwerking kan niet opnieuw worden ingediend.")
    else:
        uitwerking.status = StudentUitwerking.Status.INGELEVERD
        uitwerking.inlever_datum = timezone.now()
        uitwerking.save(update_fields=["status", "inlever_datum"])
        messages.success(request, "De uitwerking is ingediend en staat nu op read-only.")
    return redirect("dashboard")
