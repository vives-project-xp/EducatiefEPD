from django.urls import path

from . import views

app_name = "dossier"
urlpatterns = [
    path("health/", views.health, name="health"),
    path("", views.home, name="home"),
    path("casus/<int:case_id>/", views.case_detail, name="case_detail"),
    path("casus/<int:case_id>/indienen/", views.submit_student_case, name="submit_student_case"),
    path("dossier/<int:case_id>/", views.dossier, name="dossier"),
    path("docent/", views.teacher_dashboard, name="teacher_dashboard"),
    path("docent/casus/nieuw/", views.teacher_case_create, name="teacher_case_create"),
    path("docent/casus/<int:case_id>/", views.teacher_case, name="teacher_case"),
    path("docent/casus/<int:case_id>/bewerken/", views.teacher_case_edit, name="teacher_case_edit"),
    path("docent/casus/<int:case_id>/status/", views.teacher_case_transition, name="teacher_case_transition"),
    path("docent/casus/<int:case_id>/opdracht/nieuw/", views.teacher_assignment, name="teacher_assignment_create"),
    path("docent/casus/<int:case_id>/opdracht/<int:assignment_id>/", views.teacher_assignment, name="teacher_assignment_edit"),
    path("docent/casus/<int:case_id>/opdracht/<int:assignment_id>/verwijderen/", views.teacher_assignment_delete, name="teacher_assignment_delete"),
    path("docent/casus/<int:case_id>/module/nieuw/", views.teacher_module_create, name="teacher_module_create"),
    path("docent/casus/<int:case_id>/module/<int:module_id>/", views.teacher_module, name="teacher_module"),
    path("docent/casus/<int:case_id>/module/<int:module_id>/veld/nieuw/", views.teacher_module_field, name="teacher_module_field_create"),
    path("docent/casus/<int:case_id>/module/<int:module_id>/veld/<int:field_id>/", views.teacher_module_field, name="teacher_module_field_edit"),
    path("docent/casus/<int:case_id>/module/<int:module_id>/veld/<int:field_id>/verwijderen/", views.teacher_module_field_delete, name="teacher_module_field_delete"),
    path("docent/studentdossier/<int:student_case_id>/", views.teacher_student_case, name="teacher_student_case"),
    path("docent/studentdossier/<int:student_case_id>/opdracht/<int:submission_id>/", views.teacher_review_assignment, name="teacher_review_assignment"),
    path("bibliotheek/", views.library_list, name="library_list"),
    path("bibliotheek/nieuw/", views.library_template, name="library_create"),
    path("bibliotheek/<int:template_id>/", views.library_template, name="library_detail"),
    path("bibliotheek/<int:template_id>/archiveren/", views.library_archive, name="library_archive"),
    path("bibliotheek/<int:template_id>/veld/nieuw/", views.library_field, name="library_field_create"),
    path("bibliotheek/<int:template_id>/veld/<int:field_id>/", views.library_field, name="library_field_edit"),
]
