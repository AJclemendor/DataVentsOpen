from __future__ import annotations

from enum import Enum
import pytest

from datavents import enum_from_param, _enum_from_param


class Fruit(Enum):
    APPLE = "apple"
    BANANA = "banana"
    ORANGE = 3  # numeric value to test int matching


def test_enum_by_name_and_value():
    assert enum_from_param("apple", Fruit) == Fruit.APPLE
    assert enum_from_param("APPLE", Fruit) == Fruit.APPLE
    assert enum_from_param("apple ", Fruit) == Fruit.APPLE
    assert enum_from_param("ban-ana", Fruit) == Fruit.BANANA
    assert enum_from_param("banana", Fruit) == Fruit.BANANA
    # numeric value
    assert enum_from_param(3, Fruit) == Fruit.ORANGE
    assert enum_from_param("3", Fruit) == Fruit.ORANGE


def test_enum_aliases_and_defaults():
    aliases = {"app": Fruit.APPLE, "oran": "ORANGE"}
    assert enum_from_param("app", Fruit, aliases=aliases) == Fruit.APPLE
    assert enum_from_param("oran", Fruit, aliases=aliases) == Fruit.ORANGE
    # default fallback
    assert enum_from_param("unknown", Fruit, default=Fruit.BANANA) == Fruit.BANANA


def test_enum_strict_raises():
    with pytest.raises(ValueError):
        enum_from_param("unknown", Fruit, strict=True)
    with pytest.raises(ValueError):
        enum_from_param(None, Fruit, strict=True)


def test_backcompat_alias():
    assert _enum_from_param("apple", Fruit) == Fruit.APPLE

