"""Common communicator module for PyQt bindings."""

import inspect
from typing import Any, Optional

from pydantic import BaseModel, ValidationError
from typing_extensions import override

from .._internal.pydantic_utils import get_errored_fields_from_validation_error, get_updated_fields
from .._internal.utils import check_binding, check_model_type, rsetattr
from ..bindings_map import bindings_map
from ..interface import Communicator, ConnectCallbackType


def is_callable(var: Any) -> bool:
    return inspect.isfunction(var) or inspect.ismethod(var)


class PyQtCommunicator(Communicator):
    """Communicator class, that provides methods required for binding to communicate between ViewModel and View."""

    def __init__(
        self,
        pyqtobject: Any,
        viewmodel_linked_object: Any = None,
        linked_object_attributes: Any = None,
        callback_after_update: Any = None,
    ) -> None:
        super().__init__()
        self.pyqtobject = pyqtobject()
        self.viewmodel_linked_object = viewmodel_linked_object
        self.linked_object_attributes = linked_object_attributes
        self.callback_after_update = callback_after_update
        self.prefix = ""

    def _update_viewmodel_callback(self, key: Optional[str] = None, value: Any = None) -> None:
        if issubclass(type(self.viewmodel_linked_object), BaseModel):
            updates: list[str] = []
            errors: list[str] = []
            error: Any = None
            updated = True
            model = self.viewmodel_linked_object.model_copy(deep=True)
            if self.prefix and key:
                key = key.removeprefix(f"{self.prefix}.")
            rsetattr(model, key or "", value)
            try:
                new_model = model.__class__(**model.model_dump(warnings=False))
                if new_model != self.viewmodel_linked_object:
                    updates = get_updated_fields(self.viewmodel_linked_object, new_model)
                    for field, value in new_model:
                        setattr(self.viewmodel_linked_object, field, value)
                else:
                    updated = False
            except ValidationError as e:
                errors = get_errored_fields_from_validation_error(e)
                error = e
                updated = True
        elif isinstance(self.viewmodel_linked_object, dict):
            self.viewmodel_linked_object.update({key: value})
        elif is_callable(self.viewmodel_linked_object):
            self.viewmodel_linked_object(value)
        elif isinstance(self.viewmodel_linked_object, object):
            rsetattr(self.viewmodel_linked_object, key or "", value)
        else:
            raise ValueError("Cannot update", self.viewmodel_linked_object)
        if updated and self.callback_after_update:
            self.callback_after_update({"updated": updates, "errored": errors, "error": error})

    @override
    def connect(self, name: str, connector: Any) -> ConnectCallbackType:
        # connect should be called from the View side to connect a
        # GUI element (via a function to change GUI element that is passed to the connect call)
        # and a linked_object (passed during bind creation from ViewModel side)
        if not is_callable(connector):
            raise ValueError("connector should be a callable type")

        check_binding(self.viewmodel_linked_object, name)
        bindings_map[name] = self
        self.prefix = name
        self.pyqtobject.signal.connect(connector)
        if self.viewmodel_linked_object:
            return self._update_viewmodel_callback
        else:
            return None

    @override
    def update_in_view(self, value: Any, ignore_type: bool = False) -> None:
        """Update a View (GUI) when called by a ViewModel."""
        if issubclass(type(value), BaseModel) and not ignore_type:
            check_model_type(self.viewmodel_linked_object, value, 4)
        return self.pyqtobject.signal.emit(value)
