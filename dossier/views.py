from django.shortcuts import get_object_or_404, render
from .models import Case


def home(request):
    cases = Case.objects.filter(published=True).select_related("patient")
    return render(request, "dossier/home.html", {"cases": cases})


def case_detail(request, case_id):
    case = get_object_or_404(
        Case.objects.filter(published=True).prefetch_related("modules", "assignments"), id=case_id
    )
    assignments = list(case.assignments.all())
    selected_id = request.GET.get("assignment")
    selected = next((item for item in assignments if str(item.id) == selected_id), None)
    return render(request, "dossier/case_detail.html", {
        "case": case,
        "assignments": assignments,
        "selected": selected,
        "last_assignment": assignments[-1] if assignments else None,
    })


def dossier(request, case_id):
    case = get_object_or_404(
        Case.objects.filter(published=True).prefetch_related("modules", "assignments"), id=case_id
    )
    query = request.GET.get("q", "").strip().lower()
    modules = case.modules.all()
    if query:
        modules = [module for module in modules if query in module.title.lower()]
    return render(request, "dossier/dossier.html", {"case": case, "modules": modules, "query": query})
