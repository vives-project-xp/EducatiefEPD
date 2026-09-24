from django.contrib import admin

from .models import (
    Assignment,
    AssignmentSubmission,
    AuditEvent,
    Case,
    LibraryField,
    LibraryTemplate,
    Module,
    ModuleField,
    ModuleResponse,
    Patient,
    Profile,
    StudentCase,
)


class ModuleFieldInline(admin.TabularInline):
    model = ModuleField
    extra = 0


class LibraryFieldInline(admin.TabularInline):
    model = LibraryField
    extra = 0


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ["title", "patient", "course", "status", "created_by", "updated_at"]
    list_filter = ["status", "course"]
    search_fields = ["title", "patient__name", "patient__reference"]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ["title", "case", "kind", "position", "source_template_version"]
    list_filter = ["kind"]
    inlines = [ModuleFieldInline]


@admin.register(LibraryTemplate)
class LibraryTemplateAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "education", "theme", "version", "status"]
    list_filter = ["status", "category", "education", "theme"]
    search_fields = ["title", "description"]
    inlines = [LibraryFieldInline]


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "target_type", "target_id"]
    list_filter = ["action", "target_type"]
    search_fields = ["actor__username", "target_id"]
    readonly_fields = [
        "actor", "action", "target_type", "target_id", "details", "ip_address", "created_at"
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(Patient)
admin.site.register(Profile)
admin.site.register(Assignment)
admin.site.register(StudentCase)
admin.site.register(AssignmentSubmission)
admin.site.register(ModuleResponse)
