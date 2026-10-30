"""Validate API payloads and order them for the trained pipeline."""

from __future__ import annotations

import math

from housing_api.features import FEATURE_BOUNDS, FEATURE_NAMES


class ValidationError(ValueError):
    """The request body is not a usable feature payload."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _format_bound(value: float) -> str:
    return format(value, "g")


def validate_features(payload: object) -> dict[str, float]:
    """Return a float for every feature, or raise ``ValidationError``."""
    if not isinstance(payload, dict):
        raise ValidationError(["Request body must be a JSON object of feature names to numbers."])

    errors: list[str] = []
    cleaned: dict[str, float] = {}
    for name in FEATURE_NAMES:
        if name not in payload:
            errors.append(f"Missing required field '{name}'.")
            continue
        value = payload[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"'{name}' must be a JSON number.")
            continue
        number = float(value)
        if not math.isfinite(number):
            errors.append(f"'{name}' must be a finite number.")
            continue
        low, high = FEATURE_BOUNDS[name]
        if number < low or number > high:
            errors.append(
                f"'{name}' must be between {_format_bound(low)} and {_format_bound(high)}."
            )
            continue
        cleaned[name] = number

    unknown = sorted(set(payload) - set(FEATURE_NAMES))
    if unknown:
        joined = ", ".join(f"'{name}'" for name in unknown)
        errors.append(f"Unknown field(s): {joined}.")

    if errors:
        raise ValidationError(errors)
    return cleaned


def order_features(features: dict[str, float]) -> list[float]:
    """Lay validated features out in the column order the model was trained on."""
    return [features[name] for name in FEATURE_NAMES]
