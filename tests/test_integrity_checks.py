import pandas as pd
import pytest

import ispparser


class TestGetYearsFromColumnNames:
    def test_extracts_int_columns_sorted(self):
        df = pd.DataFrame({"Region": ["a"], "Technology": ["b"], 2027: [1], 2025: [2], 2026: [3]})
        assert ispparser.getYearsFromColumnNames(df) == [2025, 2026, 2027]

    def test_raises_when_no_int_columns(self):
        df = pd.DataFrame({"Region": ["a"], "Technology": ["b"], "2025": [1]})
        with pytest.raises(ValueError, match="no columns with years"):
            ispparser.getYearsFromColumnNames(df)


class TestCheckTechnologyTypesAreLegal:
    def test_passes_valid_techs(self):
        df = pd.DataFrame({"Technology": ["coal_brown", "gas_ccgt", "wind"]})
        ispparser.checkTechnologyTypesAreLegal(df)  # should not raise

    def test_rejects_digits(self):
        df = pd.DataFrame({"Technology": ["coal_brown", "gas123"]})
        with pytest.raises(ValueError, match="not mapped properly"):
            ispparser.checkTechnologyTypesAreLegal(df)

    def test_rejects_spaces(self):
        df = pd.DataFrame({"Technology": ["coal_brown", "Black Coal"]})
        with pytest.raises(ValueError, match="not mapped properly"):
            ispparser.checkTechnologyTypesAreLegal(df)

    def test_rejects_special_chars(self):
        df = pd.DataFrame({"Technology": ["coal_brown", "gas+ccgt"]})
        with pytest.raises(ValueError, match="not mapped properly"):
            ispparser.checkTechnologyTypesAreLegal(df)

    def test_underscores_are_allowed(self):
        df = pd.DataFrame({"Technology": ["gas_ccgt_ccs", "battery_VPP_charging"]})
        ispparser.checkTechnologyTypesAreLegal(df)


class TestCheckYearColumns:
    def test_passes_sequential_years(self, wide_year_df):
        ispparser.checkYearColumns(wide_year_df)  # 26 years, should not raise

    def test_rejects_too_few_years(self):
        df = pd.DataFrame({2025: [1], 2026: [1], 2027: [1]})
        with pytest.raises(ValueError, match="sequential"):
            ispparser.checkYearColumns(df)

    def test_rejects_gap_in_years(self):
        # 22 years but with a gap
        years = list(range(2025, 2035)) + list(range(2037, 2049))
        data = {y: [1.0] for y in years}
        df = pd.DataFrame(data)
        with pytest.raises(ValueError, match="sequential"):
            ispparser.checkYearColumns(df)

    def test_rejects_exactly_20_years(self):
        years = list(range(2025, 2045))  # exactly 20
        data = {y: [1.0] for y in years}
        df = pd.DataFrame(data)
        with pytest.raises(ValueError, match="sequential"):
            ispparser.checkYearColumns(df)


class TestCheckFuelTechValuesLegal:
    def test_passes_all_positive(self):
        df = pd.DataFrame({"Technology": ["wind"], 2025: [10.0], 2026: [20.0]})
        ispparser.checkFuelTechValuesLegal(df)

    def test_rejects_negative_values(self):
        df = pd.DataFrame({"Technology": ["wind"], 2025: [-10.0], 2026: [20.0]})
        with pytest.raises(ValueError, match="illegal values"):
            ispparser.checkFuelTechValuesLegal(df)

    def test_rejects_nan_values(self):
        df = pd.DataFrame({"Technology": ["wind"], 2025: [float("nan")], 2026: [20.0]})
        with pytest.raises(ValueError, match="illegal values"):
            ispparser.checkFuelTechValuesLegal(df)


class TestBuildRegionLists:
    def test_all_valid_regions(self):
        df = pd.DataFrame({"Region": ["_all", "nsw1", "qld1", "vic1", "tas1", "sa1"]})
        good, bad, missing = ispparser.buildRegionLists(df)
        assert len(good) == 6
        assert bad == []
        assert missing == []

    def test_missing_region(self):
        df = pd.DataFrame({"Region": ["_all", "nsw1", "qld1", "vic1", "sa1"]})
        good, bad, missing = ispparser.buildRegionLists(df)
        assert len(good) == 5
        assert missing == ["tas1"]

    def test_extra_bad_region(self):
        df = pd.DataFrame({"Region": ["_all", "nsw1", "qld1", "vic1", "tas1", "sa1", "nt1"]})
        good, bad, missing = ispparser.buildRegionLists(df)
        assert len(good) == 6
        assert len(bad) == 1
        assert bad[0][0] == "nt1"
        assert missing == []

    def test_raises_without_region_column(self):
        df = pd.DataFrame({"Technology": ["wind"]})
        with pytest.raises(ValueError, match="Region"):
            ispparser.buildRegionLists(df)


class TestCheckRegions:
    def test_passes_complete_regions(self):
        df = pd.DataFrame({"Region": ["_all", "nsw1", "qld1", "vic1", "tas1", "sa1"]})
        ispparser.checkRegions(df)

    def test_raises_on_missing_region(self):
        df = pd.DataFrame({"Region": ["_all", "nsw1"]})
        with pytest.raises(ValueError, match="missing regions"):
            ispparser.checkRegions(df)

    def test_raises_on_bad_region(self):
        df = pd.DataFrame({"Region": ["_all", "nsw1", "qld1", "vic1", "tas1", "sa1", "nt1"]})
        with pytest.raises(ValueError, match="illegal region"):
            ispparser.checkRegions(df)
