from django.contrib import admin
from .models import Assignment, Case, Module, Patient

admin.site.register(Patient)
admin.site.register(Case)
admin.site.register(Module)
admin.site.register(Assignment)
