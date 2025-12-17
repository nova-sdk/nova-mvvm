"""Binding module for the Panel framework."""

import inspect
from typing import Any, Callable, List, Optional, Union, cast

import param
from pydantic import BaseModel, ValidationError
from typing_extensions import override

from .. import bindings_map
from .._internal.pydantic_utils import get_errored_fields_from_validation_error, get_updated_fields
from .._internal.utils import check_binding, rgetattr, rsetattr
from ..interface import BindingInterface, ConnectCallbackType, Worker


def is_parameterized(var: Any) -> bool:
    return isinstance(var, param.Parameterized)


def is_callable(var: Any) -> bool:
    return inspect.isfunction(var) or inspect.ismethod(var)


class WidgetConnection:
    """Helper class for widget connections."""

    def __init__(self, key: str, widget: param.Parameterized, param: str) -> None:
        self.model_key = key
        self.widget = widget
        self.widget_param = param


class Communicator:
    """Communicator class, that provides methods required for binding to communicate between ViewModel and View."""

    def __init__(
        self,
        viewmodel_linked_object: Any = None,
        callback_after_update: Any = None,
    ) -> None:
        self.viewmodel_linked_object = viewmodel_linked_object
        self.viewmodel_callback_after_update = callback_after_update
        self.connector: Union[Callable[..., Any], List[WidgetConnection]] = []
        self.prefix = "None"

    def _update_viewmodel_callback(self, key: Optional[str] = None, value: Any = None) -> None:
        if issubclass(type(self.viewmodel_linked_object), BaseModel):
            updates: list[str] = []
            errors: list[str] = []
            error: Any = None
            updated = True
            model = self.viewmodel_linked_object.model_copy(deep=True)
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
        if updated and self.viewmodel_callback_after_update:
            self.viewmodel_callback_after_update({"updated": updates, "errored": errors, "error": error})
        return None

    # connector can be a dictionary, function, or parameterized object
    def connect(self, name: str, connector: Any = None) -> ConnectCallbackType:
        if isinstance(connector, List):
            check_binding(self.viewmodel_linked_object, name)
            bindings_map[name] = self
            self.prefix = name
            self.connector = connector
        elif is_callable(connector):
            self.connector = connector
            return self._update_viewmodel_callback
        else:
            raise Exception("wrong connection type, must be a function or a dictionary")

        # Register an observer on a parameterized object with specified parameters to
        # watch and call the update function on a single parameter
        if self.viewmodel_linked_object:
            # Connection on the View side should be a dictionary which has a key with string
            # specifying the attribute name in the viewmodel linked
            # the value should be a tuple with this format (parameterized_object, 'parameter', [optional,observers])
            if self.connector:
                for connection in self.connector:
                    try:
                        key = connection.model_key
                        widget = connection.widget
                        param_connector = connection.widget_param

                        if is_parameterized(widget):
                            widget.param.watch(
                                lambda event, key=key: self._update_viewmodel_callback(key=key, value=event.new),
                                param_connector,
                            )
                        else:
                            raise Exception(f"Cannot create observer for key: {key} and parameter {param_connector}")
                    except Exception:
                        raise Exception("Cannot connect", key) from None
        return None

    # Update the view based on the provided value
    def update_in_view(self, value: Any) -> None:
        if is_callable(self.connector):
            cast(Callable, self.connector)(value)
        elif self.viewmodel_linked_object:
            if is_callable(self.viewmodel_linked_object):
                self.viewmodel_linked_object(value)
            else:
                for connection in cast(List, self.connector):
                    value_to_change = rgetattr(self.viewmodel_linked_object, connection.model_key)
                    rsetattr(connection.widget, connection.widget_param, value_to_change)


class PanelBinding(BindingInterface):
    """Binding Interface implementation for Panel."""

    def new_bind(
        self, linked_object: Any = None, linked_object_arguments: Any = None, callback_after_update: Any = None
    ) -> Any:
        # each new_bind returns an object that can be used to bind a ViewModel/Model variable
        # with a corresponding GUI framework element
        # for Trame we use state to trigger GUI update and linked_object to trigger ViewModel/Model update
        return Communicator(linked_object, callback_after_update)

    @override
    def new_worker(self, task: Callable[..., Any], *args: Any, **kwargs: Any) -> Worker:
        raise Exception("Nova Panel does not yet support background tasks")
