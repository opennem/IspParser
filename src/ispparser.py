#!/usr/bin/env python3
"""ISP Workbook Parser — generates JSON from AEMO's ISP Outlook Excel workbooks."""

import pandas as pd
import openpyxl
import os
import re
import numpy as np
import json
import pytz
import zipfile
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILES_TO_PROCESS = 99

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FOLDER = os.path.join(PROJECT_ROOT, "input")
OUTPUT_FOLDER = os.path.join(PROJECT_ROOT, "output")

CACHE_FOLDER = "cache"
OUTLOOKS_FOLDER = "outlooks"

TIME_ZONE = pytz.timezone("Australia/Sydney")

# ---------------------------------------------------------------------------
# Fuel tech mappings
# ---------------------------------------------------------------------------

FUELTECH_MAPPINGS_2022 = {
    "Brown Coal": "coal_brown",
    "Black Coal": "coal_black",
    "Solar Thermal": "solar_thermal",
    "Utility-scale Solar": "solar_utility",
    "Imports": "imports",
    "Exports": "exports",
    "Distributed PV": "solar_rooftop",
    "Wind": "wind",
    "Hydro": "hydro",
    "Distributed Storage": "battery_distributed_discharging",
    "Distributed Storage Load": "battery_distributed_charging",
    "Mid-merit Gas": "gas_ccgt",
    "Mid-merit Gas with CCS": "gas_ccgt_ccs",
    "Offshore Wind": "wind_offshore",
    "Peaking Gas\\+Liquids": "gas_ocgt",
    "Hydrogen Turbine": "gas_hydrogen",
    "Utility-scale Storage": "battery_discharging",
    "Utility-scale Storage Load": "battery_charging",
    "Coordinated DER Storage": "battery_VPP_discharging",
    "Coordinated DER Storage Load": "battery_VPP_charging",
    "DSP": "demand_response",
}

FUELTECH_MAPPINGS_2024_DRAFT = {
    "Brown Coal": "coal_brown",
    "Black Coal": "coal_black",
    "Mid-merit Gas": "gas_ccgt",
    "Mid-merit Gas with CCS": "gas_ccgt_ccs",
    "Flexible Gas": "gas_ocgt",
    "Offshore Wind": "wind_offshore",
    "Wind": "wind",
    "Hydro": "hydro",
    "DSP": "demand_response",
    "Imports": "imports",
    "Exports": "exports",
    "Distributed PV": "solar_rooftop",
    "Utility-scale Solar": "solar_utility",
    "Solar Thermal": "solar_thermal",
    "Biomass": "bioenergy",
    "Hydrogen Turbine": "gas_hydrogen",
    "Utility-scale Storage": "battery_discharging",
    "Utility-scale Storage Load": "battery_charging",
    "Coordinated CER Storage": "battery_VPP_discharging",
    "Coordinated CER Storage Load": "battery_VPP_charging",
    "Passive CER Storage": "battery_distributed_discharging",
    "Passive CER Storage Load": "battery_distributed_charging",
}

FUELTECH_MAPPINGS_2024 = {
    "Brown coal": "coal_brown",
    "Black coal": "coal_black",
    "Mid-merit gas": "gas_ccgt",
    "Flexible gas with CCS": "gas_ccgt_ccs",
    "Flexible gas": "gas_ocgt",
    "Offshore wind": "wind_offshore",
    "Wind": "wind",
    "Hydro": "hydro",
    "DSP": "demand_response",
    "Imports": "imports",
    "Exports": "exports",
    "Distributed PV": "solar_rooftop",
    "Utility solar": "solar_utility",
    "Utility storage": "battery_discharging",
    "Utility storage load": "battery_charging",
    "Coordinated CER storage": "battery_VPP_discharging",
    "Coordinated CER storage load": "battery_VPP_charging",
    "Passive CER storage": "battery_distributed_discharging",
    "Passive CER storage load": "battery_distributed_charging",
    "Other renewable fuels": "bioenergy",
}

FUELTECH_MAPPINGS_2026 = {
    "Brown coal": "coal_brown",
    "Black coal": "coal_black",
    "Mid-merit gas": "gas_ccgt",
    "Flexible gas with CCS": "gas_ccgt_ccs",
    "Flexible gas": "gas_ocgt",
    "Offshore wind": "wind_offshore",
    "Wind": "wind",
    "Hydro": "hydro",
    "DSP": "demand_response",
    "Imports": "imports",
    "Exports": "exports",
    "Rooftop and other small-scale solar": "solar_rooftop",
    "Utility-scale solar": "solar_utility",
    "Utility-scale storage": "battery_discharging",
    "Utility-scale storage load": "battery_charging",
    "Coordinated CER storage": "battery_VPP_discharging",
    "Coordinated CER storage load": "battery_VPP_charging",
    "Passive CER storage": "battery_distributed_discharging",
    "Passive CER storage load": "battery_distributed_charging",
    "Other renewable fuels": "bioenergy",
}

RELEASE_FUELTECH_MAPPINGS = {
    "2022_ISP_draft": FUELTECH_MAPPINGS_2022,
    "2022_ISP_final": FUELTECH_MAPPINGS_2022,
    "2024_ISP_draft": FUELTECH_MAPPINGS_2024_DRAFT,
    "2024_ISP_final": FUELTECH_MAPPINGS_2024,
    "2026_ISP_draft": FUELTECH_MAPPINGS_2026,
}

# ---------------------------------------------------------------------------
# Cost mappings
# ---------------------------------------------------------------------------

COST_MAPPINGS_2022 = {
    "Generator Capital": "generator_capital",
    "REZ Augmentation": "rez_augmentation",
    "Flow Path Augmentation": "flow_path_augmentation",
    "FOM": "fixed_operating_and_maintenance",
    "Fuel": "fuel",
    "VOM": "variable_operating_and_maintenance",
    "DSP\\+USE": "dsp_use",
}

COST_MAPPINGS_2024 = {
    "Generator capital": "generator_capital",
    "FOM": "fixed_operating_and_maintenance",
    "Fuel": "fuel",
    "VOM": "variable_operating_and_maintenance",
    "DSP\\+USE": "dsp_use",
    "REZ augmentation": "rez_augmentation",
    "Flow path augmentation": "flow_path_augmentation",
    "Emissions cost": "emissions_cost",
}

COST_MAPPINGS_2026 = {
    "Generation, storage and electrolyser capital costs": "generator_capital",
    "Generation, storage and electrolyser FOM costs": "fixed_operating_and_maintenance",
    "Generation, storage and electrolyser VOM costs": "variable_operating_and_maintenance",
    "Generation, storage and electrolyser retirement costs": "generator_retirement",
    "Fuel costs": "fuel",
    "DSP\\+USE costs": "dsp_use",
    "Emissions costs": "emissions_cost",
    "REZ capital costs": "rez_capital",
    "REZ O&M costs": "rez_operations_and_maintenance",
    "Flow path capital costs": "flow_path_capital",
    "Flow path O&M costs": "flow_path_operations_and_maintenance",
    "Distribution capital costs": "distribution_capital",
    "Distribution O&M costs": "distribution_operations_and_maintenance",
    "System security costs": "system_security",
}

RELEASE_COST_MAPPINGS = {
    "2022_ISP_draft": COST_MAPPINGS_2022,
    "2022_ISP_final": COST_MAPPINGS_2022,
    "2024_ISP_draft": COST_MAPPINGS_2022,
    "2024_ISP_final": COST_MAPPINGS_2024,
    "2026_ISP_draft": COST_MAPPINGS_2026,
}

# ---------------------------------------------------------------------------
# Integrity checks
# ---------------------------------------------------------------------------

def getYearsFromColumnNames(frame):
    years = [col for col in frame.columns if isinstance(col, int)]
    years.sort()
    if (len(years) == 0):
        raise ValueError("ERROR: no columns with years found!")
    return years


def checkTechnologyTypesAreLegal(combined):
    technology_types = combined['Technology'].unique()
    illegals = [tech for tech in technology_types if not tech.replace('_', '').isalpha()]
    if illegals:
        raise ValueError(f'ERROR: the following technology types are not mapped properly: {illegals}')
    print("INFO: all technology types appear to be mapped properly")


def checkYearColumns(combined):
    years = getYearsFromColumnNames(combined)
    if len(years) <= 20 or not all(y2 == y1 + 1 for y1, y2 in zip(years, years[1:])):
        raise ValueError("ERROR: year columns should sequential and in format XXXX (eg. not XXXX-YY).")
    print(f"INFO: years are sequential from {years[0]} to {years[-1]}")


def checkFuelTechValuesLegal(combined):
    years = getYearsFromColumnNames(combined)
    failed_rows = combined[(combined[years] < 0).any(axis=1) | combined[years].isna().any(axis=1)]
    if not failed_rows.empty:
        print(f"ERROR: {len(failed_rows)} of {len(combined)} rows have illegal values")
        print(failed_rows.head())
        failed_tech_types = failed_rows['Technology'].unique()
        raise ValueError(f"ERROR: the following technology types have illegal values: {failed_tech_types}")
    print("INFO: all technology types have valid values")


def buildRegionLists(df):
    print("INFO: checking to see that all regions are represented and that no illegal regions are present")

    if 'Region' not in df.columns:
        raise ValueError("ERROR: frame does not have a 'Region' column")

    REGIONS = ['_all', 'qld1', 'nsw1', 'vic1', 'tas1', 'sa1']

    region_counts = df['Region'].value_counts().reset_index()
    region_counts.columns = ['Region', 'count']
    region_list = list(region_counts.itertuples(index=False, name=None))

    good_regions = []
    bad_regions = []
    missing_regions = []

    for region, count in region_list:
        if region in REGIONS:
            good_regions.append((region, count))
        else:
            bad_regions.append((region, count))

    existing_regions = set([region for region, count in region_list])
    missing_regions = [region for region in REGIONS if region not in existing_regions]

    return good_regions, bad_regions, missing_regions


def checkRegions(combined):
    good_regions, bad_regions, missing_regions = buildRegionLists(combined)

    print(f"INFO: got good regions: {good_regions}")

    if (len(missing_regions) > 0):
        raise ValueError(f"ERROR: missing regions: {missing_regions}")
    else:
        print("INFO: all regions are present")

    if (len(bad_regions) > 0):
        raise ValueError(f"ERROR: illegal region names: {bad_regions}")


def runIntegrityChecks(outlooks):
    checkRegions(outlooks)
    checkTechnologyTypesAreLegal(outlooks)
    checkYearColumns(outlooks)
    checkFuelTechValuesLegal(outlooks)

# ---------------------------------------------------------------------------
# Data transforms
# ---------------------------------------------------------------------------

def renameRegions(frame):
    frame['Region'] = frame['Region'].apply(lambda x: '_all' if x.lower() == "nem" else x.lower() + "1")
    return frame


def renameTechnologyLabels(frame, fueltech_mappings):
    for old_label, new_label in fueltech_mappings.items():
        frame['Technology'] = frame['Technology'].replace(r'^{}$'.format(old_label), new_label, regex=True)
    return frame


def renameCostLabels(frame, cost_mappings):
    for old_label, new_label in cost_mappings.items():
        frame['Technology'] = frame['Technology'].replace(r'^{}$'.format(old_label), new_label, regex=True)
    return frame


def renameYearColumnsFromStringToInteger(frame):
    count = 0
    for col in frame.columns:
        if isinstance(col, str) and re.match(r"^\d{4}$", col):
            frame.rename(columns={col: int(col)}, inplace=True)
            count += 1
    if count:
        print(f"INFO: renamed {count} year columns from string to integer")


def renameFinancialYearColumns(frame):
    print("INFO: renaming financial year columns…")
    count = 0
    for col in frame.columns:
        if isinstance(col, str) and re.match(r"^\d{4}-\d{2}$", col):
            new_col_name = int("20" + col[5:])
            frame.rename(columns={col: new_col_name}, inplace=True)
            count += 1
    if count:
        print(f"INFO: renamed {count} financial years")


def makeSpecialTechsPositive(frame):
    years = getYearsFromColumnNames(frame)

    flip_types = [
        "battery_charging",
        "battery_VPP_charging",
        "battery_distributed_charging",
        "exports",
    ]

    for tech_type in flip_types:
        tech_rows = frame[frame["Technology"] == tech_type]
        num_negative = tech_rows[(tech_rows[years] < 0).any(axis=1)].shape[0]
        if num_negative:
            print(f"INFO: {num_negative} rows with negative values found for '{tech_type}', making them positive")
            frame.loc[frame['Technology'] == tech_type, years] = frame.loc[frame['Technology'] == tech_type, years].abs()


def changeNumericColumnsToFloats(frame):
    for col in getYearsFromColumnNames(frame):
        frame[col] = frame[col].astype(float)


def multiplyBy1e3(frame):
    for col in getYearsFromColumnNames(frame):
        frame[col] = frame[col] * 1e3


def collapseSubregions(frame):
    if 'Subregion' not in frame.columns:
        return frame

    print("INFO: subregion column found, collapsing")
    before_rows = frame.shape[0]

    collapsed = frame.groupby(['CDP', 'Region', 'Technology']).sum().reset_index()
    collapsed = collapsed.drop(columns=['Subregion'])

    after_rows = collapsed.shape[0]
    print(f"INFO: collapsing subregions went from {before_rows} to {after_rows} rows")
    return collapsed


def addSummaryRegion(df):
    nem_region = df.groupby(["Scenario", "CDP", "Type", "Technology"]).sum().reset_index()
    nem_region["Region"] = "_all"

    trim_nem = nem_region[~nem_region['Technology'].isin(['imports', 'exports'])]
    trim_nem = trim_nem[~trim_nem['Type'].isin(['cost'])]

    return pd.concat([df, trim_nem], ignore_index=True)

# ---------------------------------------------------------------------------
# Loading and caching
# ---------------------------------------------------------------------------

def loadISPDataFromSheet(excel_file, sheetname):
    sheet = excel_file[sheetname]
    data = pd.DataFrame(sheet.values)

    data.columns = data.iloc[2].apply(lambda x: int(float(x)) if isinstance(x, float) else x)

    data.drop([0, 1, 2], inplace=True)
    data.dropna(how="all", inplace=True)

    nan_cols = [col for col in data.columns if col is None or (isinstance(col, float) and np.isnan(col))]
    if nan_cols:
        print(f"INFO: dropping {len(nan_cols)} empty trailing columns from '{sheetname}'")
        data = data.drop(columns=nan_cols)

    return data


def getCdpNames(release_id, file_name):
    """Read the CDPs sheet from a workbook and return a dict of CDP -> description."""
    workbook_path = os.path.join(INPUT_FOLDER, release_id, file_name)
    wb = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)

    if 'CDPs' not in wb.sheetnames:
        wb.close()
        return {}

    ws = wb['CDPs']
    cdp_names = {}
    for row in ws.iter_rows(values_only=True):
        cell_a = row[0] if row[0] else ''
        cell_b = row[1] if len(row) > 1 and row[1] else ''
        cell_a = str(cell_a).strip()
        cell_b = str(cell_b).strip()

        if re.match(r'^CDP\d+', cell_a) or cell_a == 'Counterfactual':
            clean_key = re.sub(r'\s*\(ODP\)', '', cell_a)
            if '(ODP)' in cell_a and '(ODP)' not in cell_b:
                cell_b = cell_b + ' (ODP)' if cell_b else '(ODP)'
            cdp_names[clean_key] = cell_b

    wb.close()
    return cdp_names


def check_dataframe_compatibility(dataframes):
    """
    Check if the columns of the DataFrames.
    Prints debugging information if the columns are not identical.

    :param dataframes: A list of DataFrames to compare with each other.
    :raises ValueError: If the columns are not identical.
    """
    print("INFO: checking that dataframes are all compatible")

    def print_column_details(frame, name):
        print(f"{name} columns and types:")
        for col in frame.columns:
            print(f"'{col}' ({type(col)})")

    ref_frame, ref_name = dataframes[0]
    for test_frame, test_name in dataframes:
        if set(ref_frame.columns) != set(test_frame.columns):
            print(f"\nERROR: The column names of {ref_name} and {test_name} are not identical.")

            print(f"{ref_name} columns:", list(ref_frame.columns))
            print_column_details(ref_frame, ref_name)

            print(f"{test_name} columns:", list(test_frame.columns))
            print_column_details(test_frame, test_name)

            raise ValueError(f"ERROR: The column names of {ref_name} and {test_frame.name} are not identical.")


def getWorkbookData(release_id, file_name, label):
    workbook_path = os.path.join(INPUT_FOLDER, release_id, file_name)
    print(f"\nloading release '{release_id}', scenario '{label}' from '{workbook_path}'")

    fueltech_mappings = RELEASE_FUELTECH_MAPPINGS.get(release_id)
    cost_mappings = RELEASE_COST_MAPPINGS.get(release_id)
    if fueltech_mappings is None:
        raise ValueError(f"ERROR: no fueltech mappings defined for release '{release_id}'")
    if cost_mappings is None:
        raise ValueError(f"ERROR: no cost mappings defined for release '{release_id}'")

    excel_file = openpyxl.load_workbook(workbook_path)

    print("INFO: loading generation")
    generation = loadISPDataFromSheet(excel_file, 'Generation')

    print("INFO: loading imports and exports")
    flows = loadISPDataFromSheet(excel_file, 'Imports and Exports')

    if 'Flow' in flows.columns:
        flows = flows[flows['Flow'].isin(['Imports', 'Exports'])]
        flows = flows.rename(columns={"Flow": "Technology"})
        flows.loc[flows['Technology'] == "Exports", generation.select_dtypes(include=[np.number]).columns] *= -1
    else:
        print("Column names of flows:", list(flows.columns))
        raise ValueError("ERROR: the Flows column is missing")

    print("INFO: loading capacity")
    capacities = loadISPDataFromSheet(excel_file, 'Capacity')

    print("INFO: loading emissions")
    emissions = loadISPDataFromSheet(excel_file, 'Emissions')
    emissions = emissions.drop(columns=['Total'])
    emissions.insert(2, 'Technology', 'none')

    print("INFO: loading costs")
    costs = loadISPDataFromSheet(excel_file, 'Costs')
    costs.insert(1, 'Region', 'nem')
    costs = costs.rename(columns={"Category": "Technology"})

    if release_id in ('2022_ISP_final', '2022_ISP_draft'):
        print("INFO: removing column 'Existing and Committed' from capacities")
        capacities.drop(columns=['Existing and Committed'], inplace=True)

    if release_id == '2024_ISP_final':
        capacities.drop(columns=['2023-24'], inplace=True)

    if release_id == '2024_ISP_draft':
        capacities.drop(columns=[2024], inplace=True)

    if release_id == '2026_ISP_draft':
        capacities.drop(columns=['2025-26'], inplace=True)

    if release_id == '2024_ISP_draft':
        for frame in [capacities, generation, flows, emissions, costs]:
            frame['CDP'] = frame['CDP'].str.replace(r'\s*\(ODP\)', '', regex=True)
            frame.drop(frame[frame['CDP'] == 'Least-cost DP'].index, inplace=True)

    for frame in [capacities, generation, flows, emissions, costs]:
        renameFinancialYearColumns(frame)
        changeNumericColumnsToFloats(frame)
        renameRegions(frame)

    capacities = collapseSubregions(capacities)
    generation = collapseSubregions(generation)

    check_dataframe_compatibility([
        (generation, "generation"),
        (flows, "flows"),
        (capacities, "capacities"),
        (emissions, "emissions"),
        (costs, "costs")
    ])

    energies = pd.concat([generation, flows], ignore_index=True)
    energies.insert(0, "Type", "energy")
    energies = renameTechnologyLabels(energies, fueltech_mappings)
    makeSpecialTechsPositive(energies)

    capacities.insert(1, "Type", "capacity")
    capacities = renameTechnologyLabels(capacities, fueltech_mappings)
    capacities['Technology'] = capacities['Technology'].apply(lambda x: x[:-12] if x.endswith("_discharging") else x)

    emissions.insert(1, "Type", "emissions")
    multiplyBy1e3(emissions)

    costs.insert(1, "Type", "cost")
    costs = renameCostLabels(costs, cost_mappings)

    combined = pd.concat([energies, capacities, emissions, costs], ignore_index=True)
    combined.insert(0, "Scenario", re.sub(r'\W+', '_', label.strip().lower()))

    combined = addSummaryRegion(combined)

    return combined


def loadScenariosList(release_name):
    index_file = os.path.join(INPUT_FOLDER, release_name, "scenarios.json")
    if not os.path.exists(index_file):
        raise ValueError(f"ERROR: the scenario index file '{index_file}' does not exist.")

    with open(index_file) as f:
        scenario_files = json.load(f)

    if len(scenario_files) == 0:
        raise ValueError(f"ERROR: the scenarios list from '{index_file}' is empty.")

    return scenario_files


def processGenerationOutlookFiles(release_id):
    combined_data = pd.DataFrame()
    num_files_processed = 0

    scenario_files = loadScenariosList(release_id)
    for file_info in scenario_files:
        if num_files_processed >= MAX_FILES_TO_PROCESS:
            break

        scenario_label = file_info["label"]
        file_name = file_info['file_name']
        outlook_data = getWorkbookData(release_id, file_name, scenario_label)

        combined_data = pd.concat([combined_data, outlook_data], ignore_index=True)
        num_files_processed += 1

    return combined_data


def processAndCacheOutlooks(filename_parquet, release_name):
    if os.path.exists(filename_parquet):
        print(f"WARNING: '{filename_parquet}' exists, skipping processing and will used cached version")
        return

    print(f"\nINFO: processing ISP outlook workbooks for release '{release_name}'")
    combined_data = processGenerationOutlookFiles(release_name)

    runIntegrityChecks(combined_data)

    print(f"\nwriting to cache '{filename_parquet}'")
    frame_copy = combined_data.copy()
    frame_copy.columns = frame_copy.columns.map(str)
    frame_copy.to_parquet(filename_parquet)


def loadGenerationOutlooks(release_name):
    cache_path = os.path.join(OUTPUT_FOLDER, CACHE_FOLDER)
    if not os.path.exists(cache_path):
        print("creating cache directory")
        os.makedirs(cache_path)

    filename_parquet = os.path.join(cache_path, release_name + ".outlook.parquet")

    processAndCacheOutlooks(filename_parquet, release_name)

    combined_data = pd.read_parquet(filename_parquet)
    renameYearColumnsFromStringToInteger(combined_data)
    runIntegrityChecks(combined_data)

    return combined_data

# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def compact_json(json_str):
    pattern = r'("data": \[)([\d\., \n]*)(\])'

    def replacer(match):
        start, middle, end = match.groups()
        compact_middle = middle.replace('\n', '').replace(' ', '').replace(',', ', ')
        return start + compact_middle + end

    return re.sub(pattern, replacer, json_str, flags=re.DOTALL)


def generate_id(row):
    if row['Region'] == 'nem':
        locator = "au.nem."
    else:
        locator = f"au.nem.{row['Region'].lower()}."

    if row['Type'] == 'cost':
        id = locator + f"cost.{row['Technology']}.{row['Scenario']}.{row['CDP'].lower()}"
    else:
        id = locator
        if row['Technology'] != 'none':
            id += f"fuel_tech.{row['Technology']}."
        id += f"{row['Type']}.{row['Scenario']}.{row['CDP'].lower()}"

    return id


def zipdir(path, zip_path):
    zipf = zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED)
    for root, dirs, files in os.walk(path):
        for file in files:
            zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), os.path.join(path, '..')))
    zipf.close()


RELEASES_FOLDER = "releases"


def getUnitFromType(series_type):
    if series_type == "energy":
        return "GWh"
    elif series_type == "capacity":
        return "MW"
    elif series_type == "emissions":
        return "ktCO2e"
    elif series_type == "cost":
        return "$000s"
    else:
        raise ValueError(f"ERROR: unknown type '{series_type}'")


def buildNewJSON(outlooks, release, scenario, cdp_names=None):
    data = []

    years = getYearsFromColumnNames(outlooks)
    start_year = years[0] - 1
    last_year = years[-1] - 1
    start = f"{start_year}-07-01T00:00:00+10:00"
    last = f"{last_year}-07-01T00:00:00+10:00"

    for i, row in outlooks.iterrows():
        if row['Scenario'] == scenario:
            year_data = [round(x, 1) for x in row[pd.to_numeric(row.index, errors='coerce')>=2022].tolist()]

            element = {
                "id": generate_id(row),
                "type": row['Type'],
                "network": "nem",
                "region": row['Region'],
                "fuel_tech": row['Technology'],
                "category": row['Technology'],
                "scenario": row['Scenario'],
                "pathway": row['CDP'],
                "units": getUnitFromType(row['Type']),
                "projection": {
                    "start": start,
                    "last": last,
                    "interval": "1Y",
                    "data": year_data
                }
            }

            if row['Type'] == "cost":
                del element['fuel_tech']
            else:
                del element['category']

            if row['Technology'] == 'none':
                del element['fuel_tech']

            data.append(element)

    output_obj = {
        "version": "4.2",
        "release": release,
        "created_at": datetime.now(TIME_ZONE).strftime("%Y-%m-%dT%H:%M:%S%z"),
        "messages": [ f"projections from AEMO's {release} generation outlooks" ],
    }

    if cdp_names:
        output_obj["cdp_names"] = cdp_names

    output_obj["data"] = data

    json_output = json.dumps(output_obj, indent=2)
    return compact_json(json_output)


def writeNewJSON(root, outlooks, release, scenario, cdp_names=None):
    print(f"INFO: writing {release}/{scenario}")

    json_output = buildNewJSON(outlooks, release, scenario, cdp_names)
    filename = f"{scenario}.json"
    path = os.path.join(root, filename)
    with open(path, "w") as f:
        f.write(json_output)


def writeNewJSONs(release):
    outlooks = loadGenerationOutlooks(release)

    scenario_files = loadScenariosList(release)
    cdp_names = getCdpNames(release, scenario_files[0]['file_name'])
    if cdp_names:
        print(f"INFO: extracted {len(cdp_names)} CDP names")

    output_dir = os.path.join(OUTPUT_FOLDER, RELEASES_FOLDER, release)
    print(f"INFO: creating folder {output_dir}")
    os.makedirs(output_dir, exist_ok=True)

    for scenario in outlooks['Scenario'].unique():
        writeNewJSON(output_dir, outlooks, release, scenario, cdp_names)

    distro_file = os.path.join(OUTPUT_FOLDER, RELEASES_FOLDER, f"{release}.zip")
    zipdir(output_dir, distro_file)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    writeNewJSONs("2022_ISP_draft")
    writeNewJSONs("2022_ISP_final")
    writeNewJSONs("2024_ISP_draft")
    writeNewJSONs("2024_ISP_final")
    writeNewJSONs("2026_ISP_draft")
