"""Test package for Panel bindings."""

import panel as pn
import pytest
from typing_extensions import Generator

from nova.mvvm import bindings_map
from nova.mvvm.panel_binding import PanelBinding, WidgetConnection
from tests.model import User


@pytest.fixture(scope="function", autouse=True)
def function_scoped_fixture() -> Generator[str, None]:
    yield "function"
    bindings_map.clear()


class App(pn.viewable.Viewer):
    """Test Application class."""

    def __init__(self) -> None:
        super().__init__()
        self.username = pn.widgets.TextInput(name="Name", value="name")
        self._view = pn.Column(self.username)

    def __panel__(self) -> pn.Column:
        """Overrides __panel__ method to return the view."""
        return self._view


if pn.state.served:
    pn.extension(sizing_mode="stretch_width")

    App().servable()


@pytest.fixture
def app() -> App:
    return App()


def test_panel_constructor(app: App) -> None:
    """Tests default values of App."""
    assert app.username.value == "name"


def test_panel_binding(app: App) -> None:
    """Tests binding."""
    test_object = User()

    binding = PanelBinding().new_bind(test_object)
    connections = [
        WidgetConnection("username", app.username, "value"),
    ]
    binding.connect("config", connections)
    binding.update_in_view(test_object)

    assert app.username.value == test_object.username


def test_panel_binding_same_name(app: App) -> None:
    """Creates pyqt binding for with same name, expect error."""
    test_object = User()
    test_object2 = User()

    binding = PanelBinding().new_bind(test_object)
    binding2 = PanelBinding().new_bind(test_object2)

    connections = [
        WidgetConnection("username", app.username, "value"),
    ]
    binding.connect("config", connections)
    with pytest.raises(ValueError):
        binding2.connect("config", connections)
