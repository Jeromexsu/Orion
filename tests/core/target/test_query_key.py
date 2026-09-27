
import pytest
from pydantic import ValidationError

from core.target import (
    QueryKey,
    Target,
    provides,
    query_key,
    query_key_name,
    target_type,
    validate_query_value,
)
from plugins.observed_points.position import Position
from plugins.query_keys.icao24 import Icao24
from plugins.query_keys.registration import Registration
from plugins.target.aircraft import Aircraft


def test_target_declares_query_keys_by_annotation() -> None:
    assert Aircraft.query_key_fields() == {Registration: "registration", Icao24: "icao24"}


def test_query_values_skip_empty_fields() -> None:
    bare = Aircraft(id="a", name="x", registration="B-1")
    full = Aircraft(id="b", name="y", registration="B-2", icao24="780a3b")
    assert bare.query_values() == {Registration: "B-1"}
    assert full.query_values() == {Registration: "B-2", Icao24: "780a3b"}


def test_query_values_validated_on_construction() -> None:
    with pytest.raises(ValidationError, match="not a valid icao24"):
        Aircraft(id="a", name="x", registration="B-1", icao24="NOT-HEX")


def test_validate_query_value() -> None:
    assert validate_query_value(Icao24, "780a3b") == "780a3b"
    with pytest.raises(ValidationError):
        validate_query_value(Icao24, "780A3B")


def test_same_query_key_on_two_fields_rejected_at_declaration() -> None:
    with pytest.raises(TypeError, match="provided by both"):

        @target_type("twice", observed_points=[Position])
        class Twice(Target):  # pyright: ignore[reportUnusedClass]
            a: str = provides(Icao24)
            b: str = provides(Icao24)


def test_query_key_must_be_declared() -> None:
    class Undeclared(QueryKey): ...

    with pytest.raises(TypeError, match="@query_key"):
        query_key_name(Undeclared)


def test_query_key_decorator() -> None:
    @query_key("level", value_type=int)
    class Level(QueryKey): ...

    assert (Level.name, validate_query_value(Level, "3")) == ("level", 3)
    with pytest.raises(TypeError, match="pattern only applies to str"):

        @query_key("bad", pattern="x", value_type=int)
        class Bad(QueryKey): ...  # pyright: ignore[reportUnusedClass]
