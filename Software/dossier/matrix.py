"""Versioned, bounded sheets. The saved schema, never the browser, grants rights."""

from copy import deepcopy
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from django.core.exceptions import ValidationError

MAX_ROWS, MAX_COLUMNS, MAX_CELLS = 100, 40, 2000
MAX_PAYLOAD = 512_000
TYPES = {"text", "long_text", "number", "date", "time", "datetime", "boolean", "checkbox", "select", "multiselect", "label"}
ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def blank(value):
    return value is None or value == "" or value == []


def fingerprint(field):
    schema = field.as_schema() if field and field.pk else {}
    return hashlib.sha256(json.dumps(schema, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def legacy_definition(rows, columns):
    return {
        "version": 2,
        "rows": [{"id": f"r{i}", "label": label, "height": 36} for i, label in enumerate(rows)],
        "columns": [{"id": f"c{i}", "label": label, "width": 150} for i, label in enumerate(columns)],
        "cells": {},
    }


def cell_spec(definition, row, column):
    return definition.get("cells", {}).get(row, {}).get(column, {})


def value_for(values, spec, row, column):
    cells = values.get("cells", {}) if isinstance(values, dict) else {}
    row_values = cells.get(row, {}) if isinstance(cells, dict) else {}
    return row_values.get(column, spec.get("default", "")) if isinstance(row_values, dict) else ""


def normalize_value(value, spec, *, complete=False):
    kind = spec.get("type", "text")
    if isinstance(value, str):
        value = value.strip()
    if blank(value):
        if complete and spec.get("required") and not spec.get("read_only") and kind != "label":
            raise ValidationError("Deze cel is verplicht.")
        return ""
    if kind in {"boolean", "checkbox"}:
        if type(value) is not bool:
            raise ValidationError("Kies ja of nee.")
        return value
    if kind == "multiselect":
        if not isinstance(value, list) or len(value) > 100 or any(not isinstance(v, str) or v not in spec.get("options", []) for v in value):
            raise ValidationError("Kies alleen waarden uit de keuzelijst.")
        return list(dict.fromkeys(value))
    if not isinstance(value, str) or len(value) > 10000:
        raise ValidationError("Gebruik tekst van maximaal 10.000 tekens.")
    if len(value) > spec.get("max_length", 10000):
        raise ValidationError("De tekst is langer dan toegestaan.")
    if kind == "number":
        try:
            normalized = value.replace(",", ".")
            if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", normalized):
                raise InvalidOperation
            number = Decimal(normalized)
            if not number.is_finite():
                raise InvalidOperation
            if "min" in spec and number < Decimal(spec["min"]):
                raise ValidationError(f"Minimum: {spec['min']}.")
            if "max" in spec and number > Decimal(spec["max"]):
                raise ValidationError(f"Maximum: {spec['max']}.")
            return normalized
        except (InvalidOperation, ValueError):
            raise ValidationError("Vul een getal in (komma of punt als decimaalteken, geen duizendtalscheiding).")
    if kind in {"date", "time", "datetime"}:
        # Local wall-clock values, like the existing dossier controls. No timezone conversion.
        patterns = {"date": r"\d{4}-\d{2}-\d{2}", "time": r"\d{2}:\d{2}(?::\d{2})?", "datetime": r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?"}
        try:
            if not re.fullmatch(patterns[kind], value):
                raise ValueError
            {"date": date, "time": time, "datetime": datetime}[kind].fromisoformat(value)
        except ValueError:
            raise ValidationError("Gebruik een geldige datum/tijd: JJJJ-MM-DD, UU:MM of JJJJ-MM-DDTUU:MM.")
    if kind == "select" and value not in spec.get("options", []):
        raise ValidationError("Kies een waarde uit de keuzelijst.")
    return value


def normalize_definition(value):
    """Validate metadata with explicit bounds; reject unknown executable/styling input."""
    def fail(message="De matrixindeling is ongeldig."):
        raise ValidationError(message)

    if not isinstance(value, dict) or value.get("version") != 2 or len(json.dumps(value)) > MAX_PAYLOAD:
        fail()
    if set(value) - {"version", "rows", "columns", "cells"}:
        fail()
    result = {"version": 2, "cells": {}}
    for axis, maximum, dimension, default, minimum, upper in (
        ("rows", MAX_ROWS, "height", 36, 28, 300),
        ("columns", MAX_COLUMNS, "width", 150, 70, 600),
    ):
        entries = value.get(axis)
        if not isinstance(entries, list) or not 1 <= len(entries) <= maximum:
            fail(f"Gebruik 1 tot {maximum} {('rijen' if axis == 'rows' else 'kolommen')}.")
        seen, normalized = set(), []
        for item in entries:
            if not isinstance(item, dict) or set(item) - {"id", "label", dimension}:
                fail()
            identifier, label, size = item.get("id"), item.get("label", ""), item.get(dimension, default)
            if not isinstance(identifier, str) or not ID.fullmatch(identifier) or identifier in seen or identifier in {"constructor", "prototype", "__proto__"}:
                fail("Rijen en kolommen moeten unieke, geldige IDs hebben.")
            if not isinstance(label, str) or len(label) > 180 or type(size) is not int or not minimum <= size <= upper:
                fail("Controleer de koppen en afmetingen van de matrix.")
            seen.add(identifier)
            normalized.append({"id": identifier, "label": label, dimension: size})
        result[axis] = normalized
    if len(result["rows"]) * len(result["columns"]) > MAX_CELLS:
        fail(f"Een matrix bevat maximaal {MAX_CELLS} cellen.")
    cells = value.get("cells", {})
    if not isinstance(cells, dict) or set(cells) - {r["id"] for r in result["rows"]}:
        fail()
    columns = {c["id"] for c in result["columns"]}
    for row, row_cells in cells.items():
        if not isinstance(row_cells, dict) or set(row_cells) - columns:
            fail()
        result["cells"][row] = {}
        for column, spec in row_cells.items():
            if not isinstance(spec, dict) or set(spec) - {"type", "text", "default", "required", "read_only", "placeholder", "help", "options", "min", "max", "max_length", "unit", "number_format", "decimals", "currency", "style"}:
                fail()
            spec = deepcopy(spec)
            if not isinstance(spec.get("type", "text"), str) or spec.get("type", "text") not in TYPES:
                fail("Onbekend celtype.")
            for name in ("required", "read_only"):
                if name in spec and type(spec[name]) is not bool:
                    fail()
            for name, limit in (("text", 10000), ("placeholder", 180), ("help", 500), ("unit", 30)):
                if name in spec and (not isinstance(spec[name], str) or len(spec[name]) > limit):
                    fail()
            if "max_length" in spec and (type(spec["max_length"]) is not int or not 1 <= spec["max_length"] <= 10000):
                fail()
            if spec.get("number_format", "plain") not in ("plain", "decimal", "percent", "currency") or spec.get("currency", "EUR") not in ("EUR", "USD", "GBP"):
                fail("Onbekende getalweergave.")
            if "decimals" in spec and (type(spec["decimals"]) is not int or not 0 <= spec["decimals"] <= 8):
                fail("Kies 0 tot 8 decimalen voor de weergave.")
            options = spec.get("options", [])
            if not isinstance(options, list) or len(options) > 100 or any(not isinstance(o, str) or not o.strip() or len(o) > 180 for o in options) or len(set(options)) != len(options):
                fail("Gebruik maximaal 100 unieke, niet-lege keuzeopties.")
            if spec.get("type") in {"select", "multiselect"} and not options:
                fail("Voeg keuzeopties toe aan elke keuzecel.")
            for bound in ("min", "max"):
                if bound in spec:
                    spec[bound] = normalize_value(spec[bound], {"type": "number"})
                    if blank(spec[bound]):
                        fail("Een grens moet een getal zijn.")
            if "min" in spec and "max" in spec and Decimal(spec["min"]) > Decimal(spec["max"]):
                fail("Het minimum mag niet groter zijn dan het maximum.")
            style = spec.get("style", {})
            if not isinstance(style, dict) or set(style) - {"bold", "italic", "wrap", "align", "color", "background", "border"}:
                fail()
            for name in ("bold", "italic", "wrap"):
                if name in style and type(style[name]) is not bool:
                    fail()
            for name in ("color", "background"):
                if name in style and (not isinstance(style[name], str) or not COLOR.fullmatch(style[name])):
                    fail()
            if style.get("align", "left") not in ("left", "center", "right") or style.get("border", "normal") not in ("normal", "strong", "none"):
                fail()
            if "default" in spec:
                spec["default"] = normalize_value(spec["default"], spec)
            result["cells"][row][column] = spec
    return result


def validate_values(definition, value, *, complete=False, current=None):
    """Return normalized answers and coordinate-specific errors; never mutate input."""
    errors, normalized = [], {"version": 2, "cells": {}}
    if not isinstance(value, dict) or value.get("version") != 2 or set(value) - {"version", "cells"} or not isinstance(value.get("cells"), dict) or len(json.dumps(value)) > MAX_PAYLOAD:
        return normalized, ["De matrix bevat ongeldige gegevens."], False
    rows, columns = {r["id"] for r in definition["rows"]}, {c["id"] for c in definition["columns"]}
    if set(value["cells"]) - rows or any(not isinstance(v, dict) or set(v) - columns for v in value["cells"].values()):
        return normalized, ["De matrix bevat onbekende rijen of kolommen."], False
    has_value = False
    for ri, row in enumerate(definition["rows"]):
        row_id = row["id"]
        normalized["cells"][row_id] = {}
        for ci, column in enumerate(definition["columns"]):
            col_id = column["id"]
            spec = cell_spec(definition, row_id, col_id)
            raw = value_for(value, spec, row_id, col_id)
            coordinate = f"Rij {ri + 1} ({row['label']}), kolom {ci + 1} ({column['label']})"
            if spec.get("type") == "label":
                if col_id in value["cells"].get(row_id, {}):
                    errors.append(f"{coordinate}: vaste tekst mag niet worden gewijzigd.")
                continue
            if current is not None and spec.get("read_only") and raw != value_for(current, spec, row_id, col_id):
                errors.append(f"{coordinate}: deze cel is alleen-lezen.")
            try:
                cell = normalize_value(raw, spec, complete=complete)
                normalized["cells"][row_id][col_id] = cell
                if not spec.get("read_only") and not blank(cell):
                    has_value = True
            except ValidationError as exc:
                errors.extend(f"{coordinate}: {message}" for message in exc.messages)
    return normalized, errors, has_value


def empty_values():
    return {"version": 2, "cells": {}}


def convert_base_values(old_schema, definition, data):
    """Explicit source conversion only. Reject orphaned or newly protected answers."""
    if not isinstance(data, dict):
        raise ValidationError("Bestaande matrixwaarden hebben een ongeldig formaat; herstel die eerst.")
    if old_schema.get("matrix_definition"):
        values = deepcopy(data or empty_values())
    else:
        values = empty_values()
        expected = {f"{ri}_{ci}": (f"r{ri}", f"c{ci}") for ri in range(len(old_schema.get("rows", []))) for ci in range(len(old_schema.get("columns", [])))}
        for key, value in data.items():
            if key not in expected:
                raise ValidationError("Niet-herkende bestaande matrixwaarden: omzetting afgebroken.")
            row, column = expected[key]
            values["cells"].setdefault(row, {})[column] = value
    allowed_rows = {r["id"] for r in definition["rows"]}
    allowed_cols = {c["id"] for c in definition["columns"]}
    filtered = empty_values()
    if not isinstance(values.get("cells"), dict):
        raise ValidationError("Bestaande matrixwaarden zijn ongeldig.")
    for row, cells in values["cells"].items():
        if not isinstance(cells, dict):
            raise ValidationError("Bestaande matrixwaarden zijn ongeldig.")
        for column, value in cells.items():
            spec = cell_spec(definition, row, column)
            if row not in allowed_rows or column not in allowed_cols or spec.get("type") == "label":
                if not blank(value):
                    raise ValidationError("Deze wijziging zou bestaande voorinvulling verwijderen. Maak die cellen eerst bewust leeg in het basisdossier.")
                continue
            filtered["cells"].setdefault(row, {})[column] = value
    normalized, errors, _ = validate_values(definition, filtered)
    if errors:
        raise ValidationError(["De bestaande voorinvulling past niet bij de nieuwe indeling.", *errors])
    return normalized
