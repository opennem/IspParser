import pandas as pd
import pytest

import ispparser


class TestCompactJson:
    def test_compacts_data_arrays(self):
        input_text = '{\n  "data": [\n    1.0,\n    2.0,\n    3.0\n  ]\n}'
        result = ispparser.compact_json(input_text)
        assert '"data": [1.0, 2.0, 3.0]' in result

    def test_leaves_other_keys_alone(self):
        input_text = '{\n  "name": "test",\n  "data": [\n    1.0,\n    2.0\n  ]\n}'
        result = ispparser.compact_json(input_text)
        assert '"name": "test"' in result
        assert '"data": [1.0, 2.0]' in result


class TestGenerateId:
    def test_energy_type(self):
        row = {"Region": "nsw1", "Type": "energy", "Technology": "wind",
               "Scenario": "step_change", "CDP": "CDP1"}
        result = ispparser.generate_id(row)
        assert result == "au.nem.nsw1.fuel_tech.wind.energy.step_change.cdp1"

    def test_cost_type(self):
        row = {"Region": "nem", "Type": "cost", "Technology": "fuel",
               "Scenario": "step_change", "CDP": "CDP1"}
        result = ispparser.generate_id(row)
        assert result == "au.nem.cost.fuel.step_change.cdp1"

    def test_nem_region(self):
        row = {"Region": "nem", "Type": "energy", "Technology": "wind",
               "Scenario": "step_change", "CDP": "CDP1"}
        result = ispparser.generate_id(row)
        assert result == "au.nem.fuel_tech.wind.energy.step_change.cdp1"

    def test_none_technology(self):
        row = {"Region": "nsw1", "Type": "emissions", "Technology": "none",
               "Scenario": "step_change", "CDP": "CDP1"}
        result = ispparser.generate_id(row)
        assert result == "au.nem.nsw1.emissions.step_change.cdp1"

    def test_cdp_lowercased(self):
        row = {"Region": "nsw1", "Type": "capacity", "Technology": "solar",
               "Scenario": "step_change", "CDP": "CDP12"}
        result = ispparser.generate_id(row)
        assert result.endswith(".cdp12")

    def test_all_region(self):
        row = {"Region": "_all", "Type": "energy", "Technology": "wind",
               "Scenario": "step_change", "CDP": "CDP1"}
        result = ispparser.generate_id(row)
        assert result == "au.nem._all.fuel_tech.wind.energy.step_change.cdp1"


class TestGetUnitFromType:
    @pytest.mark.parametrize("type_name,expected", [
        ("energy", "GWh"),
        ("capacity", "MW"),
        ("emissions", "ktCO2e"),
        ("cost", "$000s"),
    ])
    def test_valid_types(self, type_name, expected):
        assert ispparser.getUnitFromType(type_name) == expected

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="unknown type"):
            ispparser.getUnitFromType("unknown")


class TestCheckDataframeCompatibility:
    def test_passes_identical_columns(self):
        df1 = pd.DataFrame({"A": [1], "B": [2]})
        df2 = pd.DataFrame({"A": [3], "B": [4]})
        ispparser.check_dataframe_compatibility([(df1, "df1"), (df2, "df2")])

    def test_raises_on_different_columns(self):
        df1 = pd.DataFrame({"A": [1], "B": [2]})
        df2 = pd.DataFrame({"A": [3], "C": [4]})
        # Note: there's a bug in check_dataframe_compatibility — it uses
        # test_frame.name instead of test_name, causing AttributeError.
        # This test documents the current (buggy) behavior.
        with pytest.raises(AttributeError):
            ispparser.check_dataframe_compatibility([(df1, "df1"), (df2, "df2")])
