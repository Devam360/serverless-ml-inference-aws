"""Input validation for the prediction payload."""

from __future__ import annotations

import math

import pytest

from housing_api.features import FEATURE_BOUNDS, FEATURE_NAMES
from housing_api.preprocess import ValidationError, order_features, validate_features

VALID = {
    "MedInc": 3.5,
    "HouseAge": 20.0,
    "AveRooms": 5.0,
    "AveBedrms": 1.0,
    "Population": 1000.0,
    "AveOccup": 3.0,
    "Latitude": 37.5,
    "Longitude": -122.0,
}


def test_bounds_cover_every_feature():
    assert set(FEATURE_BOUNDS) == set(FEATURE_NAMES)


def test_valid_payload_is_ordered():
    cleaned = validate_features(dict(VALID))
    assert order_features(cleaned) == [VALID[name] for name in FEATURE_NAMES]


def test_accepts_inclusive_bounds_and_integers():
    payload = dict(VALID)
    payload["HouseAge"] = 1
    payload["Latitude"] = 32
    payload["Longitude"] = -125
    cleaned = validate_features(payload)
    assert cleaned["HouseAge"] == 1.0
    assert cleaned["Latitude"] == 32.0
    assert cleaned["Longitude"] == -125.0


def test_missing_and_unknown_fields_are_reported_together():
    payload = dict(VALID)
    del payload["MedInc"]
    payload["ZipCode"] = 94110
    with pytest.raises(ValidationError) as exc:
        validate_features(payload)
    messages = " ".join(exc.value.errors)
    assert "Missing required field 'MedInc'." in messages
    assert "Unknown field(s): 'ZipCode'." in messages


def test_rejects_strings_bools_and_non_finite_numbers():
    as_string = dict(VALID)
    as_string["MedInc"] = "3.5"
    with pytest.raises(ValidationError, match="JSON number"):
        validate_features(as_string)

    as_bool = dict(VALID)
    as_bool["HouseAge"] = True
    with pytest.raises(ValidationError, match="JSON number"):
        validate_features(as_bool)

    as_nan = dict(VALID)
    as_nan["AveOccup"] = math.nan
    with pytest.raises(ValidationError, match="finite"):
        validate_features(as_nan)


def test_rejects_out_of_range_coordinates():
    payload = dict(VALID)
    payload["Latitude"] = 10
    with pytest.raises(ValidationError) as exc:
        validate_features(payload)
    assert exc.value.errors == ["'Latitude' must be between 32 and 42.5."]


def test_rejects_non_objects():
    with pytest.raises(ValidationError, match="JSON object"):
        validate_features(["MedInc", 1])
