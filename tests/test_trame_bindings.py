"""Test package."""

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List

import pytest
import pytest_asyncio
from trame.app import get_server
from trame_server import Server

from nova.mvvm import bindings_map
from nova.mvvm._internal.utils import rgetattr, rsetdictvalue
from nova.mvvm.trame_binding import TrameBinding
from nova.mvvm.trame_binding.trame_worker import ProgressCallback

from .model import User


@pytest_asyncio.fixture(scope="function", autouse=True)  # Default scope
async def function_scoped_fixture() -> AsyncGenerator[str, None]:
    yield "function"
    bindings_map.clear()


@pytest_asyncio.fixture(scope="module")
# could not make it work wirh scope=function, so we have one server(and state) for all tests
async def server() -> AsyncGenerator[Server, None]:
    server = get_server()
    task = asyncio.create_task(server.start(exec_mode="coroutine", open_browser=False))
    await asyncio.sleep(1)  # Allow the server to initialize
    yield server
    await server.stop()
    task.cancel()


async def flush_state(server: Server, obj: str) -> None:
    with server.state:
        server.state.dirty(obj)
        server.state.flush()
    await asyncio.sleep(1)


async def update_value_in_state(input: Dict[str, Any], server: Server) -> None:
    rsetdictvalue(server.state["test_object"], input["field"], input["value"])
    await flush_state(server, "test_object")


test_cases: List[Dict[str, Any]] = [
    {
        "test_name": "update username",
        "input": {"field": "username", "value": "newname"},
        "result": {"value": "newname", "error": False},
    },
    {
        "test_name": "update email",
        "input": {"field": "email", "value": "test@test.com"},
        "result": {"value": "test@test.com", "error": False},
    },
    {
        "test_name": "empty username",
        "input": {"field": "username", "value": ""},
        "result": {"value": "default_user", "error": True},
    },
    {
        "test_name": "wrong age",
        "input": {"field": "age", "value": 20},
        "result": {"value": 30, "error": True},
    },
    {
        "test_name": "update age",
        "input": {"field": "age", "value": 35},
        "result": {"value": 35, "error": False},
    },
    {
        "test_name": "update run_numbers",
        "input": {"field": "run_numbers", "value": "1,3,5"},
        "result": {"value": [1, 3, 5], "error": False},
    },
    {
        "test_name": "wrong run_numbers",
        "input": {"field": "run_numbers", "value": "1,3,bla"},
        "result": {"value": [1, 2], "error": True},
    },
    {
        "test_name": "update ranges",
        "input": {"field": "ranges[0].min_value", "value": -1},
        "result": {"value": -1, "error": False},
    },
    # the whole model is validated for ranges (we use model_validator, so we adjust errored_field)
    {
        "test_name": "wrong ranges",
        "input": {"field": "ranges[1].min_value", "value": 10},
        "result": {"value": 2, "error": True, "errored_field": "ranges[1]"},
    },
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "input, expected_result",
    [(case["input"], case["result"]) for case in test_cases],
    ids=[case["test_name"] for case in test_cases],
)
async def test_binding_trame_to_model(server: Server, input: Dict[str, Any], expected_result: Dict[str, Any]) -> None:
    # Creates trame binding for a Pydantic object, updates Trame state and validates that the model was updated
    # or validation error occurred.
    after_update_results = {}
    test_object = User()

    async def after_update(results: Dict[str, Any]) -> None:
        after_update_results.update(results)

    binding = TrameBinding(server.state).new_bind(test_object, callback_after_update=after_update)
    binding.connect("test_object")
    binding.update_in_view(test_object)

    await update_value_in_state(input, server)

    if expected_result["error"]:
        errored_field = expected_result.get("errored_field", input["field"])
        assert errored_field in after_update_results["errored"]
    else:
        assert input["field"] in after_update_results["updated"]
    assert rgetattr(test_object, input["field"]) == expected_result["value"]


@pytest.mark.asyncio
async def test_binding_model_to_trame(server: Server) -> None:
    # Creates trame binding for a Pydantic object, updates model and validates that the Trame state was updated.
    test_object = User()

    binding = TrameBinding(server.state).new_bind(test_object)
    binding.connect("test_object")

    # object in state by default
    assert server.state["test_object"]["username"] == "default_user"

    # object in state changed when we modify the model and update
    test_object.username = "test"
    binding.update_in_view(test_object)
    assert server.state["test_object"]["username"] == "test"


@pytest.mark.asyncio
async def test_binding_same_name(server: Server) -> None:
    # Creates trame binding for with same name, expect error
    test_object = User()
    test_object2 = User()

    binding = TrameBinding(server.state).new_bind(test_object)
    binding.connect("test_object")
    binding2 = TrameBinding(server.state).new_bind(test_object2)
    with pytest.raises(ValueError):
        binding2.connect("test_object")


@pytest.mark.asyncio
async def test_binding_same_object(server: Server) -> None:
    # Creates trame binding for the same Pydantic object twice, expect error
    test_object = User()

    binding = TrameBinding(server.state).new_bind(test_object)
    binding.connect("test_object")
    with pytest.raises(ValueError):
        binding.connect("test_object1")


res = 0
progress_value: float = -1


def task(progress: ProgressCallback) -> None:
    global res
    res = 1
    progress("end", 100)
    time.sleep(1)


async def save_progress(_message: str, value: float) -> None:
    global progress_value
    progress_value = value


@pytest.mark.asyncio
async def test_trame_worker(server: Server) -> None:
    worker = TrameBinding(server.state).new_worker(task)
    worker.connect_progress(save_progress)
    worker.start()
    await asyncio.sleep(2)
    assert res == 1
    assert progress_value == 100
