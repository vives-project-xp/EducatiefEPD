"""Explicit library examples for regression tests; never loaded during app startup."""
from .models import Education, LibraryField, LibraryTemplate


def create_library_fixtures():
    education, _ = Education.objects.get_or_create(
        slug="vroedkunde", defaults={"name": "Vroedkunde"}
    )
    examples = [
        ("Dashboard", "module", "Algemeen", []),
        ("Anamnese", "questionnaire", "Opname", [
            ("Reden van opname", "long_text"), ("Huidige klachten en symptomen", "long_text"),
            ("Medische voorgeschiedenis", "long_text"),
        ]),
        ("Zwangerschapsdossier", "module", "Zwangerschap", [
            ("Zwangerschapsduur (weken)", "number"), ("Uitgerekende datum", "date"),
        ]),
        ("Partusdossier", "module", "Partus", [
            ("Start contracties", "datetime"), ("Klinische observaties", "observation"),
        ]),
        ("Klinisch redeneerplan", "matrix", "Klinisch redeneren", [
            ("Klinisch redeneerplan", "matrix"),
        ]),
        ("Uitwerking opdracht", "module", "Opdrachten", [("Uitwerking", "long_text")]),
    ]
    templates = []
    for title, category, theme, fields in examples:
        template = LibraryTemplate.objects.create(
            title=title, category=category, theme=theme, education=education,
        )
        for position, (label, field_type) in enumerate(fields):
            LibraryField.objects.create(
                template=template, label=label, key=f"veld-{position + 1}",
                field_type=field_type, position=position,
                rows=["Probleem", "Evaluatie"] if field_type == "matrix" else [],
                columns=["Beschrijving", "Motivatie"] if field_type == "matrix" else [],
            )
        templates.append(template)
    return templates
