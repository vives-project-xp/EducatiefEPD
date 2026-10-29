from dataclasses import dataclass


@dataclass(frozen=True)
class FunctionType:
    key: str
    label: str
    group: str
    takes_answer: bool
    input_type: str = "text"
    fields: tuple[str, ...] = ()


FUNCTION_TYPES = (
    FunctionType("image", "Afbeelding weergeven", "Informatief", False, fields=("image", "caption")),
    FunctionType("link", "Hyperlink", "Informatief", False, fields=("url", "buttonText")),
    FunctionType("info", "Toelichting", "Informatief", False, fields=("explanation",)),
    FunctionType("imageUpload", "Afbeelding uploaden", "Interactief", True, input_type="file"),
    FunctionType("fileUpload", "Bestand uploaden", "Interactief", True, input_type="file"),
    FunctionType("date", "Datum", "Interactief", True, input_type="date"),
    FunctionType("dateTime", "Datum en tijd", "Interactief", True, input_type="datetime-local"),
    FunctionType("number", "Getal", "Interactief", True, input_type="number", fields=("unit",)),
    FunctionType("matrix", "Matrix (maximaal 2)", "Interactief", True, input_type="matrix", fields=("matrixDefinition",)),
    FunctionType("multipleChoice", "Meerkeuze", "Interactief", True, input_type="select", fields=("options",)),
    FunctionType("text", "Tekst", "Interactief", True, input_type="text"),
    FunctionType("observation", "Observaties", "Interactief", True, fields=("required",)),
)

FUNCTION_TYPE_BY_KEY = {item.key: item for item in FUNCTION_TYPES}
FUNCTION_TYPE_CHOICES = [(item.key, item.label) for item in FUNCTION_TYPES]
LEGACY_FUNCTION_TYPE_ALIASES = {"observatie": "observation"}

# Rows created before Tijd was replaced remain readable and keep their stored answer.
LEGACY_FUNCTION_TYPES = {"time": FunctionType("time", "Tijd", "Interactief", True, input_type="time")}


def get_function_type(key):
    canonical_key = LEGACY_FUNCTION_TYPE_ALIASES.get(key, key)
    return FUNCTION_TYPE_BY_KEY.get(canonical_key) or LEGACY_FUNCTION_TYPES.get(key)


def is_display_only(key):
    item = get_function_type(key)
    return item is not None and not item.takes_answer
