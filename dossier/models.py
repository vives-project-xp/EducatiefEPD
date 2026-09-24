from django.db import models


class Patient(models.Model):
    name = models.CharField(max_length=120)
    reference = models.CharField(max_length=40, unique=True)
    image = models.CharField(max_length=240, blank=True)
    context = models.CharField(max_length=280, blank=True)

    def __str__(self):
        return self.name


class Case(models.Model):
    title = models.CharField(max_length=180)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="cases")
    course = models.CharField(max_length=180)
    published = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class Module(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=180)
    position = models.PositiveIntegerField(default=0)
    has_children = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "id"]


class Assignment(models.Model):
    class Status(models.TextChoices):
        RESUBMIT = "resubmit", "opnieuw inleveren"
        TODO = "todo", "in te leveren"
        DONE = "done", "ingediend"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=240)
    phase = models.CharField(max_length=120)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
