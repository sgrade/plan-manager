from typing import Any, Optional


def coerce_optional_int(value: Any, param_name: str) -> Optional[int]:
    """Coerce a possibly loosely-typed value to Optional[int].

    - None -> None
    - int -> int
    - float -> if integral (e.g., 1.0) return int(value); else raise ValueError
    - str -> if purely integer-like (e.g., "3" or "-2") return int(value); else raise ValueError
    - other -> raise ValueError

    Error messages are explicit about expected type and received value.
    """
    if value is None:
        return None

    # Fast-path for exact int
    if isinstance(value, int) and not isinstance(value, bool):
        return value

    # Accept floats that are mathematically integers
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ValueError(
            f"Invalid type for parameter '{param_name}': expected integer, got non-integer number {value!r}."
        )

    # Accept basic integer-like strings
    if isinstance(value, str):
        value_stripped = value.strip()
        if value_stripped.startswith(("+", "-")):
            sign = value_stripped[0]
            digits = value_stripped[1:]
        else:
            sign = ""
            digits = value_stripped
        if digits.isdigit():
            try:
                return int(sign + digits)
            except (ValueError, OverflowError):
                # Fallback to generic error if int conversion unexpectedly fails
                pass
        raise ValueError(
            f"Invalid type for parameter '{param_name}': expected integer, got string {value!r}."
        )

    raise ValueError(
        f"Invalid type for parameter '{param_name}': expected integer or null, got {type(value).__name__} {value!r}."
    )
