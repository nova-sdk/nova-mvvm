"""Pydantic utils."""

import logging
import re
from typing import Any, Tuple

from deepdiff import DeepDiff
from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo

logger = logging.getLogger(__name__)

ERROR_FIELD_NAME = "pydantic_errors"


def _format_field_name_from_tuple(input_tuple: Tuple) -> str:
    res = ""
    for item in input_tuple:
        if isinstance(item, int):
            formatted = f"[{item}]"
        elif isinstance(item, str):
            formatted = f".{item}" if res else item
        else:
            formatted = str(item)
        res += formatted
    return res


def get_errored_fields_from_validation_error(e: ValidationError) -> list[str]:
    """
    Get a list of Pydantic model fields from a Pydantic ValidationError.

    Args:
        e (ValidationError): The Pydantic ValidationError containing the validation errors.

    Returns
    -------
        list[str]: A list of nested field names (putting indices in brackets, and using dots for nested fields
        e.g. nested.ranges[0]) that failed validation.
    """
    res = []
    for error in e.errors():
        res.append(_format_field_name_from_tuple(error["loc"]))
    return res


def _remove_brackets_suffix(s: str) -> str:
    return re.sub(r"\[\d+\]$", "", s)


def get_updated_fields(old: BaseModel, new: BaseModel) -> list[str]:
    """
    Get a list of Pydantic model fields that were updated.

    Uses DeepDiff package to compare new and old models and
    then processed the results to build lists in a format we want.
    """
    diff = DeepDiff(old, new)
    updates = set()
    if "values_changed" in diff:
        # DeepDiff adds .root to the root object, we don't need that
        updates = {k.removeprefix("root.") for k in diff["values_changed"].keys()}
    if "type_changes" in diff:
        updates |= {k.removeprefix("root.") for k in diff["type_changes"].keys()}
    for item in ["iterable_item_added", "iterable_item_removed"]:
        # for added/removed items DeepDiff adds its index, we don't need that as well
        if item in diff:
            updates |= {_remove_brackets_suffix(k.removeprefix("root.")) for k in diff[item].keys()}

    return list(updates)


def get_nested_pydantic_field(model: BaseModel, field_path: str) -> FieldInfo:
    """Retrieve a nested field's metadata from a Pydantic model using a dot-separated path."""
    fields = field_path.split(".")
    current_model: Any = model

    for field in fields:
        if "[" in field:
            base = field.split("[")[0]
            current_model = getattr(current_model, base)
            for _ in range(field.count("[")):
                current_model = current_model[0]
            continue
        if issubclass(type(getattr(current_model, field)), BaseModel):
            current_model = getattr(current_model, field)
        else:
            return current_model.__class__.model_fields[field]

    raise Exception(f"Cannot find field {field_path}")
