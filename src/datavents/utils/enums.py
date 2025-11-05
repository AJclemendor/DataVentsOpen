from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, Optional, Type, TypeVar, Union


E = TypeVar("E", bound=Enum)


def _norm(s: str) -> str:
    s = s.strip().lower()
    # remove common separators entirely for tolerant matching
    return "".join(ch for ch in s if ch.isalnum())


def enum_from_param(
    value: Any,
    enum: Type[E],
    *,
    aliases: Optional[Mapping[str, Union[E, str]]] = None,
    default: Optional[E] = None,
    strict: bool = False,
) -> Optional[E]:
    """Parse flexible param input into an Enum member.

    Accepts:
    - existing enum instance
    - string matching member name (case/sep-insensitive) or member value (string/int)
    - numeric matching member.value when numeric
    - alias map: {"friendly": Enum.Member or "NAME"}

    Returns `default` when not resolvable unless `strict=True`, then raises ValueError.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        if strict and default is None:
            raise ValueError(f"Missing {enum.__name__} value")
        return default

    # Already enum
    if isinstance(value, enum):
        return value

    # Alias handling for strings
    if isinstance(value, str):
        raw = value
        key = _norm(raw)
        if aliases:
            # Try exact, normalized, and raw in alias keys
            for k in (key, raw, raw.lower()):
                if k in aliases:
                    ali = aliases[k]
                    if isinstance(ali, enum):
                        return ali
                    # If alias maps to a name string, resolve below by name
                    if isinstance(ali, str):
                        value = ali
                        key = _norm(str(ali))
                        break

        # Match by name (case/sep-insensitive)
        for member in enum:
            if _norm(member.name) == key:
                return member

        # Match by string value
        for member in enum:
            try:
                mv = member.value
                if isinstance(mv, str):
                    if _norm(mv) == key or mv.lower() == raw.lower():
                        return member
                    # Permit kebab/space variations like "ban-ana"
                    if _norm(raw) == _norm(mv):
                        return member
            except Exception:
                pass

        # Numeric string → compare against numeric values
        try:
            iv = int(raw)
            for member in enum:
                if isinstance(member.value, int) and member.value == iv:
                    return member
        except Exception:
            pass

    # Numeric direct
    if isinstance(value, (int, float)):
        iv = int(value)
        for member in enum:
            if isinstance(member.value, int) and member.value == iv:
                return member

    # Fallback: attempt string conversion and retry
    if not isinstance(value, str):
        try:
            return enum_from_param(str(value), enum, aliases=aliases, default=default, strict=strict)
        except Exception:
            pass

    if strict:
        raise ValueError(f"Could not parse {value!r} as {enum.__name__}")
    return default


def _enum_from_param(
    value: Any,
    enum: Type[E],
    *,
    aliases: Optional[Mapping[str, Union[E, str]]] = None,
    default: Optional[E] = None,
    strict: bool = False,
) -> Optional[E]:
    """Back-compat alias used in older codebases."""
    return enum_from_param(value, enum, aliases=aliases, default=default, strict=strict)
