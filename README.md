![logo](https://openelectricity.org.au/img/logo.svg)


# ISP Workbook Parser

This is a jupyter notebook used for generating JSON representations from AEMO's ISP Outlook (Excel) Workbooks.


## Disclaimer

This notebook is very much under development. It was originally written to read the 2022 final outlook workbooks, and has been progressively updated with the release of the 2024 draft and the 2024 final workbooks. 

As the notebook has been updated with each new release, no effort has been made to ensure backward compatibility with earlier outlook workbooks. However this will likely be a direction for future development as we'd like to be able to go back to the very first ISP outlooks.

## Output Files

Each scenario in a release is output as a JSON file in the `output` folder corresponding to the release. The scenario file includes the capacity, energy and emissions data for each development pathway, and each region (where available) and an `_all` region, being the sum of all regions.

For example, the `step_change` scenario from the `2022 final ISP` release will be generated to `output/releases/2024_ISP_final/step_change.json`.

## ISP Releases

#### 2022 ISP (working)

* all data in calendar years, from 2024 to 2051
* capacity includes `Existing and Committed` column
* includes emissions for NEM (which we map to `_all`)

#### 2024 ISP draft (not currently working)

* all data in calendar years
* capacity data as of 1 July in each year
* has some funky CDP names: `CDP11 (ODP)`, `Least-cost DP`

#### 2024 ISP (working)

* all data in _financial years_, from 2023-24 to 2051-52
* introduces Subregions
* now has emissions per region


## Contact

 - File an issue or contact the author on Twitter at [@simonahac](https://twitter.com/simonahac)

