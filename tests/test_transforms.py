import pandas as pd
import pytest

import ispparser


class TestRenameRegions:
    def test_renames_nem_to_all(self):
        df = pd.DataFrame({"Region": ["NEM"], 2025: [1.0]})
        result = ispparser.renameRegions(df)
        assert result["Region"].iloc[0] == "_all"

    def test_nem_case_insensitive(self):
        df = pd.DataFrame({"Region": ["nem"], 2025: [1.0]})
        ispparser.renameRegions(df)
        assert df["Region"].iloc[0] == "_all"

    def test_adds_suffix_1(self):
        df = pd.DataFrame({"Region": ["NSW", "QLD", "VIC"], 2025: [1.0, 2.0, 3.0]})
        ispparser.renameRegions(df)
        assert list(df["Region"]) == ["nsw1", "qld1", "vic1"]

    def test_mutates_in_place(self):
        df = pd.DataFrame({"Region": ["NSW"], 2025: [1.0]})
        result = ispparser.renameRegions(df)
        assert result is df
        assert df["Region"].iloc[0] == "nsw1"


class TestRenameTechnologyLabels:
    def test_applies_mapping(self, sample_fueltech_mappings):
        df = pd.DataFrame({"Technology": ["Black Coal", "Wind", "Gas CCGT"], 2025: [1, 2, 3]})
        ispparser.renameTechnologyLabels(df, sample_fueltech_mappings)
        assert list(df["Technology"]) == ["coal_black", "wind", "Gas CCGT"]

    def test_unmapped_values_unchanged(self, sample_fueltech_mappings):
        df = pd.DataFrame({"Technology": ["Unknown Tech"], 2025: [1]})
        ispparser.renameTechnologyLabels(df, sample_fueltech_mappings)
        assert df["Technology"].iloc[0] == "Unknown Tech"


class TestRenameCostLabels:
    def test_applies_cost_mapping(self):
        mapping = {"Generator Capital": "generator_capital", "Fuel": "fuel"}
        df = pd.DataFrame({"Technology": ["Generator Capital", "Fuel", "Other"], 2025: [1, 2, 3]})
        ispparser.renameCostLabels(df, mapping)
        assert list(df["Technology"]) == ["generator_capital", "fuel", "Other"]


class TestRenameYearColumnsFromStringToInteger:
    def test_converts_4digit_strings(self):
        df = pd.DataFrame({"Region": ["a"], "2025": [1], "2026": [2]})
        ispparser.renameYearColumnsFromStringToInteger(df)
        assert 2025 in df.columns
        assert 2026 in df.columns
        assert "2025" not in df.columns

    def test_ignores_financial_year_format(self):
        df = pd.DataFrame({"Region": ["a"], "2024-25": [1]})
        ispparser.renameYearColumnsFromStringToInteger(df)
        assert "2024-25" in df.columns
        assert 2024 not in df.columns

    def test_ignores_non_year_strings(self):
        df = pd.DataFrame({"Region": ["a"], "Technology": ["b"], 2025: [1]})
        ispparser.renameYearColumnsFromStringToInteger(df)
        assert "Region" in df.columns
        assert "Technology" in df.columns


class TestRenameFinancialYearColumns:
    def test_converts_financial_year(self):
        df = pd.DataFrame({"Region": ["a"], "2024-25": [1], "2049-50": [2]})
        ispparser.renameFinancialYearColumns(df)
        assert 2025 in df.columns
        assert 2050 in df.columns

    def test_ignores_plain_year_strings(self):
        df = pd.DataFrame({"Region": ["a"], "2025": [1]})
        ispparser.renameFinancialYearColumns(df)
        assert "2025" in df.columns  # should NOT be converted


class TestMakeSpecialTechsPositive:
    def test_flips_battery_charging(self):
        df = pd.DataFrame({"Technology": ["battery_charging"], 2025: [-100.0], 2026: [-200.0]})
        ispparser.makeSpecialTechsPositive(df)
        assert df[2025].iloc[0] == 100.0
        assert df[2026].iloc[0] == 200.0

    def test_flips_exports(self):
        df = pd.DataFrame({"Technology": ["exports"], 2025: [-50.0], 2026: [-60.0]})
        ispparser.makeSpecialTechsPositive(df)
        assert df[2025].iloc[0] == 50.0
        assert df[2026].iloc[0] == 60.0

    def test_leaves_other_techs_alone(self):
        df = pd.DataFrame({"Technology": ["wind"], 2025: [-10.0], 2026: [20.0]})
        ispparser.makeSpecialTechsPositive(df)
        assert df[2025].iloc[0] == -10.0  # not flipped

    def test_positive_values_unchanged(self):
        df = pd.DataFrame({"Technology": ["battery_charging"], 2025: [100.0], 2026: [200.0]})
        ispparser.makeSpecialTechsPositive(df)
        assert df[2025].iloc[0] == 100.0

    def test_flips_battery_vpp_charging(self):
        df = pd.DataFrame({"Technology": ["battery_VPP_charging"], 2025: [-30.0]})
        ispparser.makeSpecialTechsPositive(df)
        assert df[2025].iloc[0] == 30.0

    def test_flips_battery_distributed_charging(self):
        df = pd.DataFrame({"Technology": ["battery_distributed_charging"], 2025: [-40.0]})
        ispparser.makeSpecialTechsPositive(df)
        assert df[2025].iloc[0] == 40.0


class TestChangeNumericColumnsToFloats:
    def test_converts_int_columns_to_float(self):
        df = pd.DataFrame({"Region": ["a"], 2025: [100], 2026: [200]})
        ispparser.changeNumericColumnsToFloats(df)
        assert df[2025].dtype == float
        assert df[2026].dtype == float


class TestMultiplyBy1e3:
    def test_multiplies_year_columns(self):
        df = pd.DataFrame({"Region": ["a"], 2025: [1.5], 2026: [2.0]})
        ispparser.multiplyBy1e3(df)
        assert df[2025].iloc[0] == 1500.0
        assert df[2026].iloc[0] == 2000.0

    def test_does_not_affect_non_year_columns(self):
        df = pd.DataFrame({"Region": ["a"], 2025: [1.0]})
        ispparser.multiplyBy1e3(df)
        assert df["Region"].iloc[0] == "a"


class TestCollapseSubregions:
    def test_collapses_when_subregion_present(self):
        df = pd.DataFrame({
            "CDP": ["CDP1", "CDP1"],
            "Region": ["nsw1", "nsw1"],
            "Technology": ["wind", "wind"],
            "Subregion": ["north", "south"],
            2025: [10.0, 20.0],
            2026: [30.0, 40.0],
        })
        result = ispparser.collapseSubregions(df)
        assert len(result) == 1
        assert result[2025].iloc[0] == 30.0
        assert result[2026].iloc[0] == 70.0
        assert "Subregion" not in result.columns

    def test_noop_without_subregion(self):
        df = pd.DataFrame({
            "CDP": ["CDP1"],
            "Region": ["nsw1"],
            "Technology": ["wind"],
            2025: [10.0],
        })
        result = ispparser.collapseSubregions(df)
        assert result is df


class TestAddSummaryRegion:
    def test_creates_all_region(self):
        df = pd.DataFrame({
            "Scenario": ["step_change"] * 2,
            "CDP": ["CDP1"] * 2,
            "Type": ["energy"] * 2,
            "Region": ["nsw1", "qld1"],
            "Technology": ["wind"] * 2,
            2025: [40.0, 60.0],
        })
        result = ispparser.addSummaryRegion(df)
        all_rows = result[result["Region"] == "_all"]
        assert len(all_rows) == 1
        assert all_rows[2025].iloc[0] == 100.0

    def test_excludes_imports_from_all(self):
        df = pd.DataFrame({
            "Scenario": ["step_change"] * 2,
            "CDP": ["CDP1"] * 2,
            "Type": ["energy"] * 2,
            "Region": ["nsw1", "nsw1"],
            "Technology": ["wind", "imports"],
            2025: [40.0, 10.0],
        })
        result = ispparser.addSummaryRegion(df)
        all_rows = result[result["Region"] == "_all"]
        # Only wind should be in _all, not imports
        assert len(all_rows) == 1
        assert all_rows["Technology"].iloc[0] == "wind"

    def test_excludes_exports_from_all(self):
        df = pd.DataFrame({
            "Scenario": ["step_change"] * 2,
            "CDP": ["CDP1"] * 2,
            "Type": ["energy"] * 2,
            "Region": ["nsw1", "nsw1"],
            "Technology": ["wind", "exports"],
            2025: [40.0, 10.0],
        })
        result = ispparser.addSummaryRegion(df)
        all_rows = result[result["Region"] == "_all"]
        assert len(all_rows) == 1
        assert all_rows["Technology"].iloc[0] == "wind"

    def test_excludes_cost_type_from_all(self):
        df = pd.DataFrame({
            "Scenario": ["step_change"] * 2,
            "CDP": ["CDP1"] * 2,
            "Type": ["energy", "cost"],
            "Region": ["nsw1", "nsw1"],
            "Technology": ["wind", "fuel"],
            2025: [40.0, 10.0],
        })
        result = ispparser.addSummaryRegion(df)
        all_rows = result[result["Region"] == "_all"]
        assert len(all_rows) == 1
        assert all_rows["Type"].iloc[0] == "energy"
