from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("casus/<int:casus_id>/overzicht/", views.casus_overzicht, name="casus_overzicht"),
    path("casus/<int:casus_id>/dossier/", views.open_dossier, name="open_dossier"),
    path("casus/<int:casus_id>/start/", views.start_casus, name="start_casus"),
    path("uitwerking/<int:uitwerking_id>/", views.uitwerking, name="uitwerking"),
    path("uitwerking/<int:uitwerking_id>/submit/", views.submit_uitwerking, name="submit_uitwerking"),
]
