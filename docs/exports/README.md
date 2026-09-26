# Generated exports

Everything in this directory is generated from the authoritative source
artefacts in `docs/source/` so they can be reviewed and diffed in pull
requests without opening Excel or Word. **Do not hand-edit these files** —
edit the source workbook/document and regenerate:

```
python3 scripts/export_dataset.py
```

(the two `.md` files were generated once with `mammoth` from the source
`.docx` files; regenerate the same way if the source documents change).

| File | Source | Sheet/section |
|---|---|---|
| `clinical_dataset_v1.0.csv` | Clinical Dataset v1.0 FinalBatch.xlsx | Clinical Dataset (343 atomic concepts) |
| `evidence_sources.csv` | Clinical Dataset v1.0 FinalBatch.xlsx | Evidence Sources |
| `domain_summary.csv` | Clinical Dataset v1.0 FinalBatch.xlsx | Domain Summary |
| `domain_validation.csv` | Clinical Dataset v1.0 FinalBatch.xlsx | Domain Validation |
| `object_schemas.csv` | Provenance, Uncertainty & Reconciliation v1.0.xlsx | Object Schemas |
| `state_model.csv` | Provenance, Uncertainty & Reconciliation v1.0.xlsx | State Model |
| `source_authority_matrix.csv` | Provenance, Uncertainty & Reconciliation v1.0.xlsx | Source Authority Matrix |
| `conflict_taxonomy.csv` | Provenance, Uncertainty & Reconciliation v1.0.xlsx | Conflict Taxonomy |
| `reconciliation_algorithm.csv` | Provenance, Uncertainty & Reconciliation v1.0.xlsx | Reconciliation Algorithm |
| `reconciliation_test_cases.csv` | Provenance, Uncertainty & Reconciliation v1.0.xlsx | Reconciliation Test Cases |
| `architecture_register.csv` | Provenance, Uncertainty & Reconciliation v1.0.xlsx | Architecture Register (AR-001..040) |
| `fhir_au_detailed_mapping.csv` | Provenance, Uncertainty & Reconciliation v1.0.xlsx | FHIR AU Detailed Mapping |
| `scoping_review_and_requirements_v1.1.md` | Scoping Review and Requirements v1.1.docx | full document |
| `full_project_specification_v1.0.md` | Full Project Specification v1.0.docx | full document |

**Note on versions:** the FinalBatch workbook is used as the export source
for the Clinical Dataset sheets because its `Domain Validation` log covers
all 20 domains (batches 1-5), whereas the plain `v1.0` workbook only
recorded validation for the first 5 domains. The underlying 343 concept
rows are otherwise identical between the two files. Both original workbooks
are kept in `docs/source/` for provenance; only the FinalBatch one should be
treated as current.
