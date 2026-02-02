"""Module for utilities handling nested Pydantic models."""

import logging
import re
from typing import Any, List

from pydantic import ValidationError
from pydantic.fields import FieldInfo

from . import bindings_map
from ._internal.pydantic_utils import get_nested_pydantic_field

logger = logging.getLogger(__name__)

ERROR_FIELD_NAME = "pydantic_errors"


def get_field_info(field_name: str) -> FieldInfo:
    """
    Retrieve the metadata of a field from a nested Pydantic model in corresponding binding based on the field name.

    Parameters
    ----------
    field_name : str
        A dot-separated string representing the binding and the field name, which may include nested fields
        (e.g., "config.address.city.zipcode").

    Returns
    -------
    FieldInfo
        The metadata of the specified field.

    Raises
    ------
    Exception
        If the binding cannot be found in the bindings map or if the nested field cannot be found.
    """
    name = field_name.split(".")[0]
    field_name = field_name.removeprefix(f"{name}.")
    binding = bindings_map.get(name, None)
    if not binding:
        raise Exception(f"Cannot find binding for {name}")
    return get_nested_pydantic_field(binding.viewmodel_linked_object, field_name)


def validate_pydantic_parameter(name: str, value: Any) -> str | bool:
    """
    Validate a Pydantic model field using a dot-separated field path.

    Parameters
    ----------
    name : str
        A dot-separated string representing the path to the field to be validated
        (e.g., "config.address.city.zipcode").
    value : Any
        The value to set for the field and validate.

    Returns
    -------
    str | bool
        If validation fails, returns an error message indicating the validation issue.
        If validation succeeds, returns True.

    Raises
    ------
    None
    """
    object_name = name.split(".")[0]
    if object_name not in bindings_map:
        logger.warning(f"cannot find {object_name} in bindings_map")  # no error, just do not validate for now
        return True
    binding = bindings_map[object_name]
    current_model = binding.viewmodel_linked_object
    # get list of nested fields (if any) and get the corresponding model
    fields = name.split(".")[1:]
    for field in fields[:-1]:
        if "[" in field:
            base = field.split("[")[0]
            indices = re.findall(r"\[(\d+)\]", field)
            indices = [int(num) for num in indices]
            for i in indices:
                current_model = getattr(current_model, base)[i]
        else:
            current_model = getattr(current_model, field)
    final_field = fields[-1]
    indices = []
    if "[" in final_field:
        indices = re.findall(r"\[(\d+)\]", final_field)
        indices = [int(num) for num in indices]
        final_field = final_field.split("[")[0]

    # copy model so we do not modify the current one
    model = current_model.copy(deep=True)
    # force set field value
    if indices:
        target_field: List = getattr(model, final_field)
        for i in indices[:-1]:
            target_field = target_field[i]
        target_field[indices[-1]] = value
    else:
        setattr(model, final_field, value)
    # validate changed model
    try:
        model.__class__(**model.model_dump(warnings=False))
    except ValidationError as e:
        for error in e.errors():
            if (len(error["loc"]) > 0 and final_field in str(error["loc"][0])) or (
                len(error["loc"]) == 0 and e.title == current_model.__class__.__name__
            ):
                return error["msg"]
    return True
