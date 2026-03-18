#!/usr/bin/env python3
"""ISP Workbook Parser — generates JSON from AEMO's ISP Outlook Excel workbooks."""

import pandas as pd
import os
import re
import sys
import numpy as np
import json
import pytz
import zipfile
import argparse
import time
import multiprocessing
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FOLDER = os.path.join(PROJECT_ROOT, "input")
OUTPUT_FOLDER = os.path.join(PROJECT_ROOT, "output")

CACHE_FOLDER = "cache"

TIME_ZONE = pytz.timezone("Australia/Sydney")

_START_TIME = time.monotonic()
_log_lock = None
_worker_id = None
_parallel_mode = False


def log(msg):
    elapsed = time.monotonic() - _START_TIME
    if _worker_id is not None:
        line = f"[{elapsed:7.1f}s] [W{_worker_id}] {msg}"
    elif _parallel_mode:
        line = f"[{elapsed:7.1f}s] [M ] {msg}"
    else:
        line = f"[{elapsed:7.1f}s] {msg}"
    if _log_lock is not None:
        with _log_lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
    else:
        print(line)

# ---------------------------------------------------------------------------
# Report config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_config.json")

def loadReportConfig(config_path=None):
    config_file = config_path or DEFAULT_CONFIG_PATH
    with open(config_file) as f:
        return json.load(f)

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
    log("INFO: all technology types appear to be mapped properly")


def checkYearColumns(combined):
    years = getYearsFromColumnNames(combined)
    if len(years) <= 20 or not all(y2 == y1 + 1 for y1, y2 in zip(years, years[1:])):
        raise ValueError("ERROR: year columns should sequential and in format XXXX (eg. not XXXX-YY).")
    log(f"INFO: years are sequential from {years[0]} to {years[-1]}")


def checkFuelTechValuesLegal(combined):
    years = getYearsFromColumnNames(combined)
    failed_rows = combined[(combined[years] < 0).any(axis=1) | combined[years].isna().any(axis=1)]
    if not failed_rows.empty:
        log(f"ERROR: {len(failed_rows)} of {len(combined)} rows have illegal values")
        print(failed_rows.head())
        failed_tech_types = failed_rows['Technology'].unique()
        raise ValueError(f"ERROR: the following technology types have illegal values: {failed_tech_types}")
    log("INFO: all technology types have valid values")


def buildRegionLists(df):
    log("INFO: checking to see that all regions are represented and that no illegal regions are present")

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

    log(f"INFO: got good regions: {good_regions}")

    if (len(missing_regions) > 0):
        raise ValueError(f"ERROR: missing regions: {missing_regions}")
    else:
        log("INFO: all regions are present")

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
    frame['Technology'] = frame['Technology'].str.strip()
    frame['Technology'] = frame['Technology'].replace(fueltech_mappings)
    return frame


def renameCostLabels(frame, cost_mappings):
    frame['Technology'] = frame['Technology'].replace(cost_mappings)
    return frame


def renameYearColumnsFromStringToInteger(frame):
    count = 0
    for col in frame.columns:
        if isinstance(col, str) and re.match(r"^\d{4}$", col):
            frame.rename(columns={col: int(col)}, inplace=True)
            count += 1
    if count:
        log(f"INFO: renamed {count} year columns from string to integer")


def renameFinancialYearColumns(frame):
    log("INFO: renaming financial year columns…")
    count = 0
    for col in frame.columns:
        if isinstance(col, str) and re.match(r"^\d{4}-\d{2}$", col):
            new_col_name = int("20" + col[5:])
            frame.rename(columns={col: new_col_name}, inplace=True)
            count += 1
    if count:
        log(f"INFO: renamed {count} financial years")


def makeSpecialTechsPositive(frame):
    years = getYearsFromColumnNames(frame)

    flip_types = [
        "battery_charging",
        "battery_VPP_charging",
        "battery_distributed_charging",
        "pumped_hydro_charging",
        "exports",
    ]

    for tech_type in flip_types:
        tech_rows = frame[frame["Technology"] == tech_type]
        num_negative = tech_rows[(tech_rows[years] < 0).any(axis=1)].shape[0]
        if num_negative:
            log(f"INFO: {num_negative} rows with negative values found for '{tech_type}', making them positive")
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

    log("INFO: subregion column found, collapsing")
    before_rows = frame.shape[0]

    collapsed = frame.groupby(['CDP', 'Region', 'Technology']).sum().reset_index()
    collapsed = collapsed.drop(columns=['Subregion'])

    after_rows = collapsed.shape[0]
    log(f"INFO: collapsing subregions went from {before_rows} to {after_rows} rows")
    return collapsed


def addSummaryRegion(df):
    nem_region = df.groupby(["Scenario", "CDP", "Type", "Technology"]).sum().reset_index()
    nem_region["Region"] = "_all"

    trim_nem = nem_region[~nem_region['Technology'].isin(['imports', 'exports'])]
    trim_nem = trim_nem[~trim_nem['Type'].isin(['cost'])]

    log(f"INFO: adding NEM summary region ({len(trim_nem)} rows added)")
    return pd.concat([df, trim_nem], ignore_index=True)

# ---------------------------------------------------------------------------
# Loading helpers (calamine-based)
# ---------------------------------------------------------------------------

def readSheet(excel_file, sheetname):
    """Read a sheet from an open ExcelFile, returning a raw DataFrame (no header)."""
    return pd.read_excel(excel_file, sheet_name=sheetname, header=None)


def loadISPDataFromSheet(excel_file, sheetname):
    data = readSheet(excel_file, sheetname)

    data.columns = data.iloc[2].apply(lambda x: int(float(x)) if isinstance(x, float) else x)

    data.drop([0, 1, 2], inplace=True)
    data.dropna(how="all", inplace=True)

    nan_cols = [col for col in data.columns if col is None or (isinstance(col, float) and np.isnan(col))]
    if nan_cols:
        log(f"INFO: dropping {len(nan_cols)} empty trailing columns from '{sheetname}'")
        data = data.drop(columns=nan_cols)

    log(f"INFO: loaded {len(data)} rows from '{sheetname}'")
    return data


# ---------------------------------------------------------------------------
# 2018 format loaders
# ---------------------------------------------------------------------------

def loadISPDataFromSheet2018(excel_file, sheetname):
    """Load a sheet from a 2018 ISP workbook. Header at row 1, data from row 2."""
    data = readSheet(excel_file, sheetname)

    data.columns = data.iloc[1]
    data.drop([0, 1], inplace=True)
    data.dropna(how="all", inplace=True)

    # Remove repeat header rows
    data = data[data.iloc[:, 0] != 'Region']

    # Forward-fill Region
    data['Region'] = data['Region'].ffill()

    # Filter out Total rows and footnotes
    tech_col = data.columns[1]
    data = data[data[tech_col].notna()]
    data = data[~data[tech_col].astype(str).str.contains('Total', na=False)]
    data = data[~data[tech_col].astype(str).str.startswith('*', na=False)]

    # Filter out NEM rows (will be recalculated by addSummaryRegion)
    data = data[data['Region'] != 'NEM']

    # Drop nan columns
    nan_cols = [col for col in data.columns if col is None or (isinstance(col, float) and np.isnan(col))]
    if nan_cols:
        data = data.drop(columns=nan_cols)

    log(f"INFO: loaded {len(data)} rows from '{sheetname}'")
    return data


def getWorkbookData2018(release_id, file_name, label, release_config, input_folder=None):
    input_dir = input_folder or INPUT_FOLDER
    workbook_path = os.path.join(input_dir, release_id, file_name)
    log(f"\nloading release '{release_id}', scenario '{label}' from '{workbook_path}'")

    fueltech_mappings = release_config["fueltech_mappings"]
    cost_mappings = release_config.get("cost_mappings", {})

    excel_file = pd.ExcelFile(workbook_path, engine="calamine")

    log("INFO: loading capacity (NEMInstalledCapacity Data)")
    capacities = loadISPDataFromSheet2018(excel_file, 'NEMInstalledCapacity Data')

    log("INFO: loading energy (NEMEnergyGenerated Data)")
    energies = loadISPDataFromSheet2018(excel_file, 'NEMEnergyGenerated Data')

    log("INFO: loading costs (GenerationInvestment)")
    costs = loadCosts2018(excel_file)

    # Add synthetic CDP (no development paths in 2018)
    for frame in [capacities, energies, costs]:
        frame.insert(0, 'CDP', 'default')

    for frame in [capacities, energies, costs]:
        renameFinancialYearColumns(frame)
        changeNumericColumnsToFloats(frame)
        renameRegions(frame)

    energies.insert(1, "Type", "energy")
    energies = renameTechnologyLabels(energies, fueltech_mappings)
    makeSpecialTechsPositive(energies)

    capacities.insert(1, "Type", "capacity")
    capacities = renameTechnologyLabels(capacities, fueltech_mappings)
    capacities['Technology'] = capacities['Technology'].apply(lambda x: x[:-12] if x.endswith("_discharging") else x)

    costs.insert(1, "Type", "cost")
    costs = renameCostLabels(costs, cost_mappings)

    combined = pd.concat([energies, capacities, costs], ignore_index=True)
    combined.insert(0, "Scenario", re.sub(r'\W+', '_', label.strip().lower()))

    combined = addSummaryRegion(combined)

    return combined


def loadCosts2018(excel_file):
    """Load GenerationInvestment sheet from 2018 workbook as a single cost category."""
    data = readSheet(excel_file, 'GenerationInvestment')

    data.columns = data.iloc[1]
    data.drop([0, 1], inplace=True)
    data.dropna(how="all", inplace=True)

    # Drop nan columns
    nan_cols = [col for col in data.columns if col is None or (isinstance(col, float) and np.isnan(col))]
    if nan_cols:
        data = data.drop(columns=nan_cols)

    # Filter out footnotes
    data = data[~data['Region'].astype(str).str.startswith('*', na=False)]
    data = data[data['Region'].notna()]

    # Sum across regions to get NEM total
    year_cols = [c for c in data.columns if c != 'Region']
    for c in year_cols:
        data[c] = pd.to_numeric(data[c], errors='coerce')
    totals = data[year_cols].sum()

    result = pd.DataFrame([totals])
    result.insert(0, 'Technology', 'Generation Investment')
    result.insert(0, 'Region', 'nem')

    # Convert from $M to $000s
    for c in year_cols:
        result[c] = result[c] * 1000

    log(f"INFO: loaded costs for {len(year_cols)} year columns")
    return result


# ---------------------------------------------------------------------------
# 2020 format loaders
# ---------------------------------------------------------------------------

def loadISPDataFromSheet2020(excel_file, sheetname):
    """Load a _2 sheet from a 2020 ISP workbook. Same header layout as 2022+."""
    data = loadISPDataFromSheet(excel_file, sheetname)

    # Keep only valid region rows (filter out totals, headers, footnotes)
    valid_regions = {'NSW', 'QLD', 'VIC', 'SA', 'TAS'}
    data = data[data['Region'].isin(valid_regions)]

    log(f"INFO: loaded {len(data)} rows from '{sheetname}'")
    return data


def loadCosts2020(excel_file, cost_sheet_map):
    """Load and combine 2020 cost sheets into a single costs DataFrame."""
    cost_frames = []

    for sheet_name, category_name in cost_sheet_map.items():
        log(f"INFO: loading cost sheet '{sheet_name}' as '{category_name}'")
        data = readSheet(excel_file, sheet_name)

        def parse_cost_col_header(x):
            if isinstance(x, float):
                return int(x)
            if isinstance(x, str) and re.match(r"^\d{4}-\d{2}$", x):
                return int("20" + x[5:])
            return x
        data.columns = data.iloc[2].apply(parse_cost_col_header)
        data.drop([0, 1, 2], inplace=True)
        data.dropna(how="all", inplace=True)

        nan_cols = [col for col in data.columns if col is None or (isinstance(col, float) and np.isnan(col))]
        if nan_cols:
            data = data.drop(columns=nan_cols)

        year_cols = [c for c in data.columns if isinstance(c, int)]

        for c in year_cols:
            data[c] = pd.to_numeric(data[c], errors='coerce').fillna(0)

        # Filter to NEM rows if they exist, otherwise sum all rows
        first_col = data.columns[0]
        if 'NEM' in data[first_col].values:
            data = data[data[first_col] == 'NEM']

        # Sum year columns across all remaining rows, clamping rounding errors to zero
        totals = data[year_cols].sum().clip(lower=0)
        row = pd.DataFrame([totals])
        row.insert(0, 'Technology', category_name)
        row.insert(0, 'Region', 'nem')
        cost_frames.append(row)

    return pd.concat(cost_frames, ignore_index=True)


def getWorkbookData2020(release_id, file_name, label, release_config, input_folder=None):
    input_dir = input_folder or INPUT_FOLDER
    workbook_path = os.path.join(input_dir, release_id, file_name)
    log(f"\nloading release '{release_id}', scenario '{label}' from '{workbook_path}'")

    fueltech_mappings = release_config["fueltech_mappings"]
    cost_mappings = release_config.get("cost_mappings", {})

    # Extract DP name from filename
    dp_match = re.search(r'\(DP(\d+)\)', file_name)
    cdp = f"DP{dp_match.group(1)}" if dp_match else "default"

    excel_file = pd.ExcelFile(workbook_path, engine="calamine")

    log("INFO: loading capacity")
    capacities = loadISPDataFromSheet2020(excel_file, 'Capacity_2')

    log("INFO: loading generation")
    generation = loadISPDataFromSheet2020(excel_file, 'Generation_2')

    if 'Emissions_2' in excel_file.sheet_names:
        log("INFO: loading emissions")
        emissions_raw = loadISPDataFromSheet(excel_file, 'Emissions_2')
        # Emissions sheet has 'Emissions' as first column, rename to Region
        first_col = emissions_raw.columns[0]
        emissions_raw = emissions_raw.rename(columns={first_col: 'Region'})
        emissions_raw = emissions_raw[emissions_raw['Region'].notna()]
        emissions_raw = emissions_raw[emissions_raw['Region'] != 'Region']
        if 'Total' in emissions_raw.columns:
            emissions_raw = emissions_raw.drop(columns=['Total'])
        emissions_raw.insert(1, 'Technology', 'none')
    else:
        log("INFO: no Emissions_2 sheet found, skipping emissions")
        emissions_raw = None

    log("INFO: loading costs")
    cost_sheet_map = release_config.get("cost_sheet_map", {
        'VOMCost_2': 'VOM',
        'FOMCost_2': 'FOM',
        'FuelCost_2': 'Fuel',
        'BuildCost_2': 'Build',
        'RehabCost_2': 'Rehab',
        'DSPCost_2': 'DSP+USE',
        'REZTxCost_2': 'REZ Transmission',
        'ICTxCost_2': 'IC Transmission',
    })
    costs = loadCosts2020(excel_file, cost_sheet_map)

    # Drop capacity columns
    for col in release_config.get("capacity_columns_to_drop", []):
        if col in capacities.columns:
            log(f"INFO: removing column '{col}' from capacities")
            capacities.drop(columns=[col], inplace=True)

    # Add CDP
    frames = [capacities, generation, costs] + ([emissions_raw] if emissions_raw is not None else [])
    for frame in frames:
        frame.insert(0, 'CDP', cdp)

    for frame in frames:
        renameFinancialYearColumns(frame)
        changeNumericColumnsToFloats(frame)
        renameRegions(frame)

    generation.insert(1, "Type", "energy")
    generation = renameTechnologyLabels(generation, fueltech_mappings)
    makeSpecialTechsPositive(generation)

    capacities.insert(1, "Type", "capacity")
    capacities = renameTechnologyLabels(capacities, fueltech_mappings)
    capacities['Technology'] = capacities['Technology'].apply(lambda x: x[:-12] if x.endswith("_discharging") else x)

    if emissions_raw is not None:
        emissions_raw.insert(1, "Type", "emissions")
        multiplyBy1e3(emissions_raw)

    costs.insert(1, "Type", "cost")
    costs = renameCostLabels(costs, cost_mappings)

    # Emissions is NEM-only, so handle addSummaryRegion separately to avoid duplicates
    non_emissions = pd.concat([generation, capacities, costs], ignore_index=True)
    non_emissions.insert(0, "Scenario", re.sub(r'\W+', '_', label.strip().lower()))
    non_emissions = addSummaryRegion(non_emissions)

    if emissions_raw is not None:
        emissions_raw.insert(0, "Scenario", re.sub(r'\W+', '_', label.strip().lower()))
        combined = pd.concat([non_emissions, emissions_raw], ignore_index=True)
    else:
        combined = non_emissions

    return combined


def getCdpNames(release_id, file_name, input_folder=None):
    """Read the CDPs sheet from a workbook and return a dict of CDP -> description."""
    input_dir = input_folder or INPUT_FOLDER
    workbook_path = os.path.join(input_dir, release_id, file_name)
    ef = pd.ExcelFile(workbook_path, engine="calamine")

    if 'CDPs' not in ef.sheet_names:
        log(f"INFO: no CDPs sheet found in '{file_name}'")
        return {}

    data = pd.read_excel(ef, sheet_name='CDPs', header=None)
    cdp_names = {}
    for _, row in data.iterrows():
        cell_a = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
        cell_b = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ''

        if re.match(r'^CDP\d+', cell_a) or cell_a == 'Counterfactual':
            clean_key = re.sub(r'\s*\(ODP\)', '', cell_a)
            if '(ODP)' in cell_a and '(ODP)' not in cell_b:
                cell_b = cell_b + ' (ODP)' if cell_b else '(ODP)'
            cdp_names[clean_key] = cell_b

    log(f"INFO: found {len(cdp_names)} CDP names in '{file_name}'")
    return cdp_names


def check_dataframe_compatibility(dataframes):
    """
    Check if the columns of the DataFrames.
    Prints debugging information if the columns are not identical.

    :param dataframes: A list of DataFrames to compare with each other.
    :raises ValueError: If the columns are not identical.
    """
    log("INFO: checking that dataframes are all compatible")

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


def getWorkbookData(release_id, file_name, label, release_config, input_folder=None):
    input_dir = input_folder or INPUT_FOLDER
    workbook_path = os.path.join(input_dir, release_id, file_name)
    log(f"\nloading release '{release_id}', scenario '{label}' from '{workbook_path}'")

    fueltech_mappings = release_config["fueltech_mappings"]
    cost_mappings = release_config["cost_mappings"]

    excel_file = pd.ExcelFile(workbook_path, engine="calamine")

    log("INFO: loading generation")
    generation = loadISPDataFromSheet(excel_file, 'Generation')

    log("INFO: loading imports and exports")
    flows = loadISPDataFromSheet(excel_file, 'Imports and Exports')

    if 'Flow' in flows.columns:
        flows = flows[flows['Flow'].isin(['Imports', 'Exports'])]
        flows = flows.rename(columns={"Flow": "Technology"})
        flows.loc[flows['Technology'] == "Exports", generation.select_dtypes(include=[np.number]).columns] *= -1
    else:
        print("Column names of flows:", list(flows.columns))
        raise ValueError("ERROR: the Flows column is missing")

    log("INFO: loading capacity")
    capacities = loadISPDataFromSheet(excel_file, 'Capacity')

    log("INFO: loading emissions")
    emissions = loadISPDataFromSheet(excel_file, 'Emissions')
    emissions = emissions.drop(columns=['Total'])
    emissions.insert(2, 'Technology', 'none')

    log("INFO: loading costs")
    costs = loadISPDataFromSheet(excel_file, 'Costs')
    costs.insert(1, 'Region', 'nem')
    costs = costs.rename(columns={"Category": "Technology"})

    for col in release_config.get("capacity_columns_to_drop", []):
        log(f"INFO: removing column '{col}' from capacities")
        capacities.drop(columns=[col], inplace=True)

    if release_config.get("cdp_strip_odp", False):
        for frame in [capacities, generation, flows, emissions, costs]:
            frame['CDP'] = frame['CDP'].str.replace(r'\s*\(ODP\)', '', regex=True)

    for cdp_val in release_config.get("cdp_drop_values", []):
        for frame in [capacities, generation, flows, emissions, costs]:
            frame.drop(frame[frame['CDP'] == cdp_val].index, inplace=True)

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


# ---------------------------------------------------------------------------
# Parallel workbook processing
# ---------------------------------------------------------------------------

def _init_worker(lock):
    """Initialise the shared log lock in each worker process."""
    global _log_lock
    _log_lock = lock


def _run_with_worker_id(worker_id, args):
    """Wrapper that sets worker_id before processing a workbook."""
    global _worker_id
    _worker_id = worker_id
    try:
        return _process_single_workbook(args)
    finally:
        _worker_id = None


def _process_single_workbook(args):
    """Worker function for ProcessPoolExecutor — processes one workbook."""
    release_id, file_name, scenario_label, release_config, fmt, input_folder = args[:6]
    if fmt == "2018":
        return getWorkbookData2018(release_id, file_name, scenario_label, release_config, input_folder=input_folder)
    elif fmt == "2020":
        return getWorkbookData2020(release_id, file_name, scenario_label, release_config, input_folder=input_folder)
    else:
        return getWorkbookData(release_id, file_name, scenario_label, release_config, input_folder=input_folder)


def processGenerationOutlookFiles(release_id, release_config, max_to_process=None, no_concurrency=False):
    fmt = release_config.get("format", "standard")
    scenarios = release_config["scenarios"]
    total_scenarios = len(scenarios)
    effective_total = min(total_scenarios, max_to_process) if max_to_process else total_scenarios
    log(f"INFO: processing {effective_total} of {total_scenarios} scenario workbooks (format: {fmt})")

    work_items = []
    for file_info in scenarios[:effective_total]:
        work_items.append((
            release_id,
            file_info['file_name'],
            file_info['label'],
            release_config,
            fmt,
            INPUT_FOLDER,
        ))

    if no_concurrency or len(work_items) == 1:
        if no_concurrency and len(work_items) > 1:
            log(f"INFO: processing {len(work_items)} workbooks sequentially (--no-concurrency)")
        results = [_process_single_workbook(item) for item in work_items]
    else:
        global _parallel_mode
        _parallel_mode = True
        lock = multiprocessing.Lock()
        max_workers = min(len(work_items), os.cpu_count() or 4)
        log(f"INFO: launching {len(work_items)} workers in parallel")
        with ProcessPoolExecutor(max_workers=max_workers, initializer=_init_worker, initargs=(lock,)) as executor:
            futures = [
                executor.submit(_run_with_worker_id, idx, item)
                for idx, item in enumerate(work_items, 1)
            ]
            results = [f.result() for f in futures]

    combined_data = pd.concat(results, ignore_index=True)
    return combined_data


def processAndCacheOutlooks(filename_parquet, release_name, release_config, use_cache=False, max_to_process=None, no_concurrency=False):
    if use_cache and os.path.exists(filename_parquet):
        log(f"INFO: '{filename_parquet}' exists, using cached version (--use-cache)")
        return

    log(f"\nINFO: processing ISP outlook workbooks for release '{release_name}'")
    combined_data = processGenerationOutlookFiles(release_name, release_config, max_to_process=max_to_process, no_concurrency=no_concurrency)

    log(f"INFO: combined data has {len(combined_data)} rows and {len(combined_data.columns)} columns")
    runIntegrityChecks(combined_data)

    log(f"\nwriting to cache '{filename_parquet}'")
    frame_copy = combined_data.copy()
    frame_copy.columns = frame_copy.columns.map(str)
    frame_copy.to_parquet(filename_parquet)


def loadGenerationOutlooks(release_name, release_config, use_cache=False, max_to_process=None, no_concurrency=False):
    cache_path = os.path.join(OUTPUT_FOLDER, CACHE_FOLDER)
    if not os.path.exists(cache_path):
        log("creating cache directory")
        os.makedirs(cache_path)

    filename_parquet = os.path.join(cache_path, release_name + ".outlook.parquet")

    processAndCacheOutlooks(filename_parquet, release_name, release_config, use_cache=use_cache, max_to_process=max_to_process, no_concurrency=no_concurrency)

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
            year_data = [round(x, 1) for x in row[years].tolist()]

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

    log(f"INFO: generated {len(data)} data series for scenario '{scenario}'")

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
    log(f"INFO: writing {release}/{scenario}")

    json_output = buildNewJSON(outlooks, release, scenario, cdp_names)
    filename = f"{scenario}.json"
    path = os.path.join(root, filename)
    with open(path, "w") as f:
        f.write(json_output)


def writeNewJSONs(release, release_config, use_cache=False, max_to_process=None, no_concurrency=False):
    outlooks = loadGenerationOutlooks(release, release_config, use_cache=use_cache, max_to_process=max_to_process, no_concurrency=no_concurrency)

    cdp_names = getCdpNames(release, release_config["scenarios"][0]['file_name'])
    if cdp_names:
        log(f"INFO: extracted {len(cdp_names)} CDP names")

    output_dir = os.path.join(OUTPUT_FOLDER, RELEASES_FOLDER, release)
    log(f"INFO: creating folder {output_dir}")
    os.makedirs(output_dir, exist_ok=True)

    for scenario in outlooks['Scenario'].unique():
        writeNewJSON(output_dir, outlooks, release, scenario, cdp_names)

    distro_file = os.path.join(OUTPUT_FOLDER, RELEASES_FOLDER, f"{release}.zip")
    zipdir(output_dir, distro_file)
    log(f"INFO: created zip archive at '{distro_file}'")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ISP Workbook Parser")
    parser.add_argument("--use-cache", action="store_true",
                        help="Use cached parquet files instead of reprocessing workbooks")
    parser.add_argument("--input", default=INPUT_FOLDER,
                        help=f"Input folder containing ISP workbooks (default: {INPUT_FOLDER})")
    parser.add_argument("--output", default=OUTPUT_FOLDER,
                        help=f"Output folder for generated files (default: {OUTPUT_FOLDER})")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH,
                        help=f"Path to report config JSON (default: {DEFAULT_CONFIG_PATH})")
    parser.add_argument("--max-to-process", type=int, default=None,
                        help="Max number of scenario workbooks to process per release (default: no limit)")
    parser.add_argument("--no-concurrency", action="store_true",
                        help="Disable parallel processing and run workbooks sequentially")
    args = parser.parse_args()

    INPUT_FOLDER = args.input
    OUTPUT_FOLDER = args.output

    config = loadReportConfig(config_path=args.config)
    releases = list(config.items())
    log(f"\nINFO: {len(releases)} releases to process")
    for idx, (release_id, release_config) in enumerate(releases, 1):
        log(f"\n{'='*60}")
        log(f"INFO: processing release '{release_id}' ({idx} of {len(releases)})")
        log(f"{'='*60}")
        writeNewJSONs(release_id, release_config, use_cache=args.use_cache, max_to_process=args.max_to_process, no_concurrency=args.no_concurrency)
