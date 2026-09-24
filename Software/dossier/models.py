from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TEACHER = "teacher", "Docent"
        ADMIN = "admin", "Beheerder"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="epd_profile"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    education = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"


class Patient(models.Model):
    class Gender(models.TextChoices):
        FEMALE = "female", "Vrouw"
        MALE = "male", "Man"
        OTHER = "other", "Anders"
        UNKNOWN = "unknown", "Niet gespecificeerd"

    name = models.CharField(max_length=120)
    reference = models.CharField(max_length=40, unique=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20, choices=Gender.choices, default=Gender.UNKNOWN, blank=True
    )
    image = models.CharField(max_length=240, blank=True)
    context = models.CharField(max_length=280, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_patients",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class Case(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Concept"
        PUBLISHED = "published", "Gepubliceerd"
        ARCHIVED = "archived", "Gearchiveerd"

    title = models.CharField(max_length=180)
    patient = models.OneToOneField(Patient, on_delete=models.PROTECT, related_name="case")
    course = models.CharField(max_length=180)
    introduction = models.TextField(blank=True)
    learning_objectives = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_cases",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-updated_at"]

    @property
    def published(self):
        return self.status == self.Status.PUBLISHED

    def publish(self):
        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()
        self.archived_at = None

    def move_to_draft(self):
        self.status = self.Status.DRAFT
        self.archived_at = None

    def archive(self):
        self.status = self.Status.ARCHIVED
        self.archived_at = timezone.now()

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class LibraryTemplate(models.Model):
    class Category(models.TextChoices):
        MODULE = "module", "Dossiermodule"
        QUESTIONNAIRE = "questionnaire", "Vragenlijst"
        MATRIX = "matrix", "Matrix"

    class Status(models.TextChoices):
        ACTIVE = "active", "Actief"
        ARCHIVED = "archived", "Gearchiveerd"

    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=24, choices=Category.choices)
    education = models.CharField(max_length=120, blank=True)
    theme = models.CharField(max_length=120, blank=True)
    instructions = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    is_fixed = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="library_templates",
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.title} (v{self.version})"


class Module(models.Model):
    class Kind(models.TextChoices):
        INFORMATION = "information", "Informatie"
        FORM = "form", "Formulier"
        QUESTIONNAIRE = "questionnaire", "Vragenlijst"
        MATRIX = "matrix", "Matrix"
        NOTES = "notes", "Vrije notities"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=180)
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.FORM)
    instructions = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    base_data = models.JSONField(default=dict, blank=True)
    position = models.PositiveIntegerField(default=0)
    source_template = models.ForeignKey(
        LibraryTemplate,
        on_delete=models.SET_NULL,
        related_name="case_copies",
        null=True,
        blank=True,
    )
    source_template_version = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.case}: {self.title}"


class FieldDefinition(models.Model):
    class FieldType(models.TextChoices):
        SHORT_TEXT = "short_text", "Korte tekst"
        LONG_TEXT = "long_text", "Vrije tekst"
        NUMBER = "number", "Numeriek veld"
        DATE = "date", "Datum"
        DATETIME = "datetime", "Datum en tijd"
        SELECT = "select", "Keuzelijst"
        OBSERVATION = "observation", "Observaties"
        MATRIX = "matrix", "Matrix"

    label = models.CharField(max_length=180)
    key = models.SlugField(max_length=80)
    field_type = models.CharField(max_length=24, choices=FieldType.choices)
    help_text = models.CharField(max_length=280, blank=True)
    required = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    options = models.JSONField(default=list, blank=True)
    rows = models.JSONField(default=list, blank=True)
    columns = models.JSONField(default=list, blank=True)

    class Meta:
        abstract = True
        ordering = ["position", "id"]

    def clean(self):
        if self.field_type == self.FieldType.SELECT and not self.options:
            raise ValidationError({"options": "Een keuzelijst heeft minstens één optie nodig."})
        if self.field_type == self.FieldType.MATRIX and (not self.rows or not self.columns):
            raise ValidationError("Een matrix heeft minstens één rij en één kolom nodig.")

    def as_schema(self):
        return {
            "label": self.label,
            "key": self.key,
            "type": self.field_type,
            "help_text": self.help_text,
            "required": self.required,
            "position": self.position,
            "options": self.options,
            "rows": self.rows,
            "columns": self.columns,
        }


class ModuleField(FieldDefinition):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="fields")

    class Meta(FieldDefinition.Meta):
        constraints = [
            models.UniqueConstraint(fields=["module", "key"], name="unique_module_field_key")
        ]

    def __str__(self):
        return f"{self.module}: {self.label}"


class LibraryField(FieldDefinition):
    template = models.ForeignKey(
        LibraryTemplate, on_delete=models.CASCADE, related_name="fields"
    )

    class Meta(FieldDefinition.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["template", "key"], name="unique_library_field_key"
            )
        ]

    def __str__(self):
        return f"{self.template}: {self.label}"


class Assignment(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=240)
    phase = models.CharField(max_length=120)
    content = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.case}: {self.phase}"


class StudentCase(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Bezig"
        SUBMITTED = "submitted", "Ingediend"
        REVIEWED = "reviewed", "Beoordeeld"

    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name="student_cases")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_cases"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    case_title = models.CharField(max_length=180, blank=True)
    course = models.CharField(max_length=180, blank=True)
    introduction = models.TextField(blank=True)
    learning_objectives = models.TextField(blank=True)
    patient_name = models.CharField(max_length=120, blank=True)
    patient_reference = models.CharField(max_length=40, blank=True)
    patient_image = models.CharField(max_length=240, blank=True)
    patient_context = models.CharField(max_length=280, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["case", "student"], name="unique_student_case")
        ]

    @property
    def locked(self):
        return self.status in {self.Status.SUBMITTED, self.Status.REVIEWED}

    @property
    def progress(self):
        total = self.assignment_submissions.count()
        if not total:
            return 0
        completed = self.assignment_submissions.exclude(
            status=AssignmentSubmission.Status.TODO
        ).count()
        return round(completed / total * 100)

    def __str__(self):
        return f"{self.student.get_username()} - {self.case_title or self.case}"


class AssignmentSubmission(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "In te leveren"
        SUBMITTED = "submitted", "Ingediend"
        RESUBMIT = "resubmit", "Opnieuw inleveren"
        APPROVED = "approved", "Goedgekeurd"

    student_case = models.ForeignKey(
        StudentCase, on_delete=models.CASCADE, related_name="assignment_submissions"
    )
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.SET_NULL,
        related_name="submissions",
        null=True,
        blank=True,
    )
    phase = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=240, blank=True)
    content = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    answer = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student_case", "assignment"], name="unique_assignment_submission"
            )
        ]

    def hydrate_from_source(self):
        if self.assignment:
            self.phase = self.assignment.phase
            self.title = self.assignment.title
            self.content = self.assignment.content
            self.position = self.assignment.position


class ModuleResponse(models.Model):
    student_case = models.ForeignKey(
        StudentCase, on_delete=models.CASCADE, related_name="module_responses"
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.SET_NULL,
        related_name="responses",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180, blank=True)
    kind = models.CharField(max_length=24, choices=Module.Kind.choices, default=Module.Kind.FORM)
    instructions = models.TextField(blank=True)
    schema = models.JSONField(default=list, blank=True)
    position = models.PositiveIntegerField(default=0)
    data = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student_case", "module"], name="unique_module_response"
            )
        ]

    def hydrate_from_source(self):
        if self.module:
            self.title = self.module.title
            self.kind = self.module.kind
            self.instructions = self.module.instructions
            self.position = self.module.position
            self.schema = [field.as_schema() for field in self.module.fields.all()]


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="epd_audit_events",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=80, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at}: {self.action}"
