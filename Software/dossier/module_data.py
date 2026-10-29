"""Parse dossier forms and validate saved snapshot data without changing it."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json

from django.core.exceptions import PermissionDenied
from .matrix import empty_values, validate_values


def valid_observation(value):
    if not isinstance(value, dict):
        return False
    timestamp = value.get("timestamp")
    text = value.get("value")
    if not isinstance(timestamp, str) or not isinstance(text, str) or not text.strip():
        return False
    if not isinstance(value.get("note", ""), str):
        return False
    try:
        datetime.fromisoformat(timestamp)
    except ValueError:
        return False
    return True


def validate_module_data(schema, data, *, require_complete=False):
    """Use the supplied schema (a student's snapshot for student work)."""
    errors = {}
    for field in schema:
        key, field_type = field["key"], field["type"]
        value = data.get(key, "")
        error = None
        has_value = False
        if field_type == "observation":
            value = data.get(key, [])
            if not isinstance(value, list) or not all(valid_observation(item) for item in value):
                error = "Controleer het tijdstip en de waarde van de observaties."
            else:
                has_value = bool(value)
        elif field_type == "matrix":
            if field.get("matrix_definition"):
                _, matrix_errors, has_value = validate_values(
                    field["matrix_definition"], data.get(key, empty_values()), complete=require_complete,
                )
                if require_complete and field.get("required") and not has_value:
                    matrix_errors.append("Vul minstens één bewerkbare cel in.")
                if matrix_errors:
                    errors[key] = matrix_errors
                continue
            value = data.get(key, {})
            if not isinstance(value, dict):
                error = "De matrix bevat ongeldige gegevens."
            else:
                cells = [
                    value.get(f"{row}_{column}", "")
                    for row, _ in enumerate(field.get("rows", []))
                    for column, _ in enumerate(field.get("columns", []))
                ]
                if not all(isinstance(cell, str) for cell in cells):
                    error = "De matrix bevat ongeldige gegevens."
                else:
                    has_value = any(cell.strip() for cell in cells)
        elif not isinstance(value, str):
            error = "Dit veld bevat een ongeldige waarde."
        else:
            value = value.strip()
            has_value = bool(value)
            if has_value:
                if field_type == "number":
                    try:
                        if not Decimal(value).is_finite():
                            raise InvalidOperation
                    except InvalidOperation:
                        error = "Vul een geldig getal in."
                elif field_type in {"date", "datetime"}:
                    try:
                        (date if field_type == "date" else datetime).fromisoformat(value)
                    except ValueError:
                        error = "Vul een geldige datum in." if field_type == "date" else "Vul een geldig tijdstip in."
                elif field_type == "select" and value not in field.get("options", []):
                    error = "Kies een waarde uit de keuzelijst."
        if not error and require_complete and field.get("required") and not has_value:
            error = {
                "matrix": "Vul minstens één cel in.",
                "observation": "Voeg minstens één observatie toe.",
            }.get(field_type, "Dit veld is verplicht.")
        if error:
            errors[key] = [error]
    return errors


@dataclass
class ModuleFormResult:
    data: dict
    display_data: dict
    pending_observations: dict
    errors: dict
    added_observations: list


def parse_module_form(post, schema, current_data, *, edit_readonly=False):
    """Prepare one all-or-nothing draft save, including pending observations.

    Raw form values remain separate from normalized storage values so an invalid
    field cannot erase the user's other edits or an observation awaiting retry.
    """
    data = deepcopy(current_data)
    display_data = deepcopy(current_data)
    pending = {}
    pending_errors = {}
    added = []
    action = post.get("action", "save")
    observation_key = action.split(":", 1)[1] if action.startswith("add_observation:") else None
    observation_keys = {field["key"] for field in schema if field["type"] == "observation"}
    if observation_key is not None and observation_key not in observation_keys:
        raise PermissionDenied

    for field in schema:
        key, field_type = field["key"], field["type"]
        if field_type == "observation":
            entry = {
                name: post.get(f"observation_{name}_{key}", "")
                for name in ("timestamp", "value", "note")
            }
            pending[key] = entry
            if key == observation_key or any(value.strip() for value in entry.values()):
                normalized = {name: value.strip() for name, value in entry.items()}
                if not valid_observation(normalized):
                    pending_errors[key] = ["Geef een geldig tijdstip en een observatie op."]
                elif isinstance(data.get(key, []), list):
                    data[key] = [*data.get(key, []), normalized]
                    added.append(key)
            continue
        if field_type == "matrix":
            if field.get("matrix_definition"):
                stored = current_data.get(key, empty_values())
                raw = post.get(f"matrix_{key}")
                try:
                    values = json.loads(raw) if raw is not None else deepcopy(stored)
                except (ValueError, TypeError, RecursionError):
                    pending_errors[key] = ["De matrixinvoer is ongeldig of te groot. Kopieer uw invoer en herlaad de pagina."]
                    continue
                normalized, matrix_errors, _ = validate_values(field["matrix_definition"], values, current=None if edit_readonly else stored)
                display_data[key] = values
                data[key] = normalized
                if matrix_errors:
                    pending_errors[key] = matrix_errors
                continue
            stored = current_data.get(key, {})
            stored = stored if isinstance(stored, dict) else {}
            raw = {
                f"{row}_{column}": post.get(f"field_{key}_{row}_{column}", stored.get(f"{row}_{column}", ""))
                for row, _ in enumerate(field.get("rows", []))
                for column, _ in enumerate(field.get("columns", []))
            }
            display_data[key] = raw
            data[key] = {cell: value.strip() if isinstance(value, str) else value for cell, value in raw.items()}
        else:
            raw = post.get(f"field_{key}", current_data.get(key, ""))
            display_data[key] = raw
            data[key] = raw.strip() if isinstance(raw, str) else raw

    errors = validate_module_data(schema, data)
    for key, messages in pending_errors.items():
        errors.setdefault(key, []).extend(messages)
    return ModuleFormResult(data, display_data, pending, errors, added)
