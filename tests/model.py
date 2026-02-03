"""The package contains Pydantic models uses for tests."""

from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class NestedList(BaseModel):
    """A Pydantic model with a validation rule for a nested list."""

    values: List[List[int]] = Field(default=[[0], [0], [0]], title="Set Less Than Zero For Error")

    @field_validator("values", mode="after")
    @classmethod
    def validate_values(cls, values: List[List[int]]) -> List[List[int]]:
        for inner_list in values:
            for value in inner_list:
                if value < 0:
                    raise ValueError("Value must be >= 0")

        return values


class Range(BaseModel):
    """A Pydantic model for range with a model validation rule."""

    min_value: int = Field(default=0, title="Min Val")
    max_value: int = Field(default=10, title="Max Val")

    @model_validator(mode="after")  # before mode - runs after Pydantic internal validation
    def validate_min_less_than_max(self) -> "Range":
        min_value = self.min_value
        max_value = self.max_value
        if min_value is not None and max_value is not None and min_value >= max_value:
            raise ValueError("min value must be less than max value")
        return self


class User(BaseModel):
    """User model for tests."""

    username: str = Field(
        default="default_user", min_length=2, title="User Name", description="hint", examples=["user"]
    )
    email: Optional[str] = Field(default=None, title="Email Address")
    age: int = Field(default=30, gt=20)
    ranges: List[Range] = Field(
        default_factory=lambda: [
            Range(min_value=0, max_value=1),
            Range(min_value=2, max_value=3),
            Range(min_value=4, max_value=5),
        ],
        title="Ranges",
    )
    run_numbers: Optional[List[int]] = Field(
        default_factory=lambda: [1, 2], title="List of run numbers", examples=["1,2,3"]
    )

    @field_validator("run_numbers", mode="before")  # before mode - runs before Pydantic internal validation
    @classmethod
    def split_string_to_list(cls, v: Any) -> List[int]:
        try:
            if isinstance(v, str):
                return [int(x) for x in v.split(",")]  # Converts each to integer
        except Exception:
            raise ValueError("Please input comma-separated list of integers") from None
        return v
