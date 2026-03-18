import pandas as pd
import pytest


@pytest.fixture
def generation_df():
    """Pre-transform DataFrame with CDP, Region, Technology + year columns."""
    return pd.DataFrame({
        "CDP": ["CDP1", "CDP1", "CDP1"],
        "Region": ["NSW", "QLD", "VIC"],
        "Technology": ["Black Coal", "Wind", "Solar"],
        2025: [100.0, 200.0, 300.0],
        2026: [110.0, 210.0, 310.0],
        2027: [120.0, 220.0, 320.0],
    })


@pytest.fixture
def combined_df():
    """Full combined DataFrame shape with Scenario, Type, CDP, Region, Technology + year columns."""
    return pd.DataFrame({
        "Scenario": ["step_change"] * 6,
        "Type": ["energy", "energy", "energy", "capacity", "capacity", "capacity"],
        "CDP": ["CDP1"] * 6,
        "Region": ["_all", "nsw1", "qld1", "_all", "nsw1", "qld1"],
        "Technology": ["wind", "wind", "wind", "wind", "wind", "wind"],
        2025: [100.0, 40.0, 60.0, 50.0, 20.0, 30.0],
        2026: [110.0, 45.0, 65.0, 55.0, 22.0, 33.0],
        2027: [120.0, 50.0, 70.0, 60.0, 25.0, 35.0],
    })


def make_wide_year_df(start=2025, end=2050, regions=None):
    """Helper to create a DataFrame with many year columns (for checkYearColumns tests)."""
    if regions is None:
        regions = ["_all", "nsw1", "qld1", "vic1", "tas1", "sa1"]
    years = list(range(start, end + 1))
    rows = []
    for region in regions:
        row = {"Region": region, "Technology": "wind"}
        for y in years:
            row[y] = 1.0
        rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture
def wide_year_df():
    """DataFrame with >20 sequential year columns and all required regions."""
    return make_wide_year_df()


@pytest.fixture
def sample_fueltech_mappings():
    return {
        "Black Coal": "coal_black",
        "Brown Coal": "coal_brown",
        "Wind": "wind",
        "Solar": "solar",
    }
