"""Feature contract shared by training and the prediction API.

Column names and order match ``sklearn.datasets.fetch_california_housing``.
Bounds cover 99.9% of the 1990 census block groups and reject coordinates or
counts that cannot describe a California block group.
"""

from __future__ import annotations

FEATURE_NAMES: tuple[str, ...] = (
    "MedInc",
    "HouseAge",
    "AveRooms",
    "AveBedrms",
    "Population",
    "AveOccup",
    "Latitude",
    "Longitude",
)

FEATURE_BOUNDS: dict[str, tuple[float, float]] = {
    "MedInc": (0.0, 20.0),
    "HouseAge": (1.0, 60.0),
    "AveRooms": (0.5, 50.0),
    "AveBedrms": (0.2, 15.0),
    "Population": (1.0, 40000.0),
    "AveOccup": (0.5, 20.0),
    "Latitude": (32.0, 42.5),
    "Longitude": (-125.0, -114.0),
}

FEATURE_DESCRIPTIONS: dict[str, str] = {
    "MedInc": "Median income in the block group, in tens of thousands of USD",
    "HouseAge": "Median house age in the block group, in years",
    "AveRooms": "Average number of rooms per household",
    "AveBedrms": "Average number of bedrooms per household",
    "Population": "Block group population",
    "AveOccup": "Average number of household members",
    "Latitude": "Block group latitude",
    "Longitude": "Block group longitude",
}

TARGET_NAME = "MedHouseVal"
TARGET_UNITS = "100,000 USD (1990 census median house value)"
DATASET_NAME = "sklearn.datasets.fetch_california_housing"
