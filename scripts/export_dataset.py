#!/usr/bin/env python3
"""Export key sheets from the source workbooks in docs/source/ into flat,
diffable CSV files under docs/exports/.

The xlsx workbooks in docs/source/ remain the authoritative artefacts (per
the Full Project Specification, "Document control"). These CSV exports exist
only so the dataset can be reviewed and diffed in pull requests without
opening Excel. Re-run this script and commit the result whenever a source
workbook changes.

Usage: python3 scripts/export_dataset.py
"""
import csv
import pathlib

import openpyxl

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "docs" / "source"
EXPORT_DIR = REPO_ROOT / "docs" / "exports"

# (workbook filename, sheet name, output csv filename)
EXPORTS = [
    (
        "Perioperative_Conversational_AI_Clinical_Dataset_v1.0_FinalBatch.xlsx",
        "Clinical Dataset",
        "clinical_dataset_v1.0.csv",
    ),
    (
        "Perioperative_Conversational_AI_Clinical_Dataset_v1.0_FinalBatch.xlsx",
        "Evidence Sources",
        "evidence_sources.csv",
    ),
    (
        "Perioperative_Conversational_AI_Clinical_Dataset_v1.0_FinalBatch.xlsx",
        "Domain Summary",
        "domain_summary.csv",
    ),
    (
        "Perioperative_Conversational_AI_Clinical_Dataset_v1.0_FinalBatch.xlsx",
        "Domain Validation",
        "domain_validation.csv",
    ),
    (
        "Perioperative_AI_Provenance_Uncertainty_Reconciliation_v1.0.xlsx",
        "Object Schemas",
        "object_schemas.csv",
    ),
    (
        "Perioperative_AI_Provenance_Uncertainty_Reconciliation_v1.0.xlsx",
        "State Model",
        "state_model.csv",
    ),
    (
        "Perioperative_AI_Provenance_Uncertainty_Reconciliation_v1.0.xlsx",
        "Source Authority Matrix",
        "source_authority_matrix.csv",
    ),
    (
        "Perioperative_AI_Provenance_Uncertainty_Reconciliation_v1.0.xlsx",
        "Conflict Taxonomy",
        "conflict_taxonomy.csv",
    ),
    (
        "Perioperative_AI_Provenance_Uncertainty_Reconciliation_v1.0.xlsx",
        "Reconciliation Algorithm",
        "reconciliation_algorithm.csv",
    ),
    (
        "Perioperative_AI_Provenance_Uncertainty_Reconciliation_v1.0.xlsx",
        "Reconciliation Test Cases",
        "reconciliation_test_cases.csv",
    ),
    (
        "Perioperative_AI_Provenance_Uncertainty_Reconciliation_v1.0.xlsx",
        "Architecture Register",
        "architecture_register.csv",
    ),
    (
        "Perioperative_AI_Provenance_Uncertainty_Reconciliation_v1.0.xlsx",
        "FHIR AU Detailed Mapping",
        "fhir_au_detailed_mapping.csv",
    ),
]


def export_sheet(workbook_path: pathlib.Path, sheet_name: str, out_path: pathlib.Path) -> None:
    wb = openpyxl.load_workbook(workbook_path, data_only=True)
    ws = wb[sheet_name]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in ws.iter_rows(values_only=True):
            if row == (None,) * len(row):
                continue
            writer.writerow(["" if cell is None else cell for cell in row])


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    for workbook_name, sheet_name, out_name in EXPORTS:
        workbook_path = SOURCE_DIR / workbook_name
        out_path = EXPORT_DIR / out_name
        export_sheet(workbook_path, sheet_name, out_path)
        print(f"wrote {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
