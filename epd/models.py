from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        DOCENT = "docent", "Docent"
        STUDENT = "student", "Student"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)


class FictievePatient(models.Model):
    class BiologicalSex(models.TextChoices):
        VROUW = "vrouw", "Vrouw"
        MAN = "man", "Man"
        ANDERS = "anders", "Anders"

    voornaam = models.CharField(max_length=100)
    achternaam = models.CharField(max_length=100)
    geboortedatum = models.DateField()
    biologisch_geslacht = models.CharField(max_length=20, choices=BiologicalSex.choices)
    context_beschrijving = models.CharField(max_length=200, blank=True)
    foto_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.voornaam} {self.achternaam}"


class BasisCasus(models.Model):
    class PublicationStatus(models.TextChoices):
        VERBORGEN = "verborgen", "Verborgen"
        OPEN = "open", "Open"

    docent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="basiscasussen")
    patient = models.OneToOneField(FictievePatient, on_delete=models.CASCADE, related_name="casus")
    titel = models.CharField(max_length=200)
    inleiding = models.TextField(blank=True)
    leerdoelen = models.TextField(blank=True)
    afdeling = models.CharField(max_length=100, blank=True)
    rol = models.CharField(max_length=100, blank=True)
    opdracht_instructie = models.TextField()
    publicatie_status = models.CharField(max_length=20, choices=PublicationStatus.choices, default=PublicationStatus.VERBORGEN)
    inlever_deadline = models.DateTimeField()
    aangemaakt_op = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-aangemaakt_op"]

    def __str__(self):
        return self.titel


class BasisCasusData(models.Model):
    casus = models.ForeignKey(BasisCasus, on_delete=models.CASCADE, related_name="data")
    sjabloon_onderdeel_id = models.CharField(max_length=100)
    waarde = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["casus", "sjabloon_onderdeel_id"], name="unique_basis_data_component")
        ]


class StudentUitwerking(models.Model):
    class Status(models.TextChoices):
        GESTART = "gestart", "Gestart"
        INGELEVERD = "ingeleverd", "Ingeleverd"
        BEOORDEELD = "beoordeeld", "Beoordeeld"

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="uitwerkingen")
    casus = models.ForeignKey(BasisCasus, on_delete=models.CASCADE, related_name="uitwerkingen")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.GESTART)
    start_datum = models.DateTimeField(auto_now_add=True)
    inlever_datum = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "casus"], name="unique_student_casus")
        ]
        ordering = ["-start_datum"]


class StudentUitwerkingData(models.Model):
    uitwerking = models.ForeignKey(StudentUitwerking, on_delete=models.CASCADE, related_name="data")
    sjabloon_onderdeel_id = models.CharField(max_length=100)
    waarde = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["uitwerking", "sjabloon_onderdeel_id"], name="unique_student_data_component")
        ]
