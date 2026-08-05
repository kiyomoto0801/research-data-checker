# Research Data Checker

A lightweight Python tool that:

- reads CSV and Excel datasets;
- generates descriptive statistics for numeric variables;
- summarizes categorical variables;
- reports missing values, duplicate rows, constant columns, negative values, and infinite values;
- optionally checks whether ID columns uniquely identify rows;
- exports results to Excel and text.

## Installation

```bash
pip install -r requirements.txt
```

## Basic usage

```bash
python research_data_checker.py sample_data.csv
```

The following files are created:

```text
output/
├── summary.xlsx
└── warnings.txt
```

## Change the missing-value warning threshold

The default threshold is 10%.

```bash
python research_data_checker.py sample_data.csv --missing-threshold 0.20
```

## Check panel-data identifiers

For example, to check whether `household_id × year` uniquely identifies each row:

```bash
python research_data_checker.py sample_data.csv --id-cols household_id year
```

## Read a specific Excel sheet

```bash
python research_data_checker.py data.xlsx --sheet Sheet1
```

## Notes

A warning does not automatically mean that the data is incorrect.  
For example, negative values may be valid for profit, growth, or temperature variables.
Always review warnings using the variable definition and research design.
