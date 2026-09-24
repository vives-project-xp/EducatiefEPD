from django.urls import path
from . import views

app_name = "dossier"
urlpatterns = [
    path("", views.home, name="home"),
    path("casus/<int:case_id>/", views.case_detail, name="case_detail"),
    path("dossier/<int:case_id>/", views.dossier, name="dossier"),
]
