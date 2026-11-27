"""Loads Clinical Dataset v1.0 (343 atomic concepts) from
docs/exports/clinical_dataset_v1.0.csv into Requirement definitions.

This is the "clinical_dataset_version" side of the ReleaseManifest made
concrete and loadable: the gap engine evaluates RequirementState against
these definitions, not against the spreadsheet directly.
"""
from __future__ import annotations

import csv
import pathlib
from functools import lru_cache

from periop_core.enums import RequirementClass
from periop_core.models import Requirement

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DEFAULT_DATASET_CSV = REPO_ROOT / "docs" / "exports" / "clinical_dataset_v1.0.csv"


def load_requirements(csv_path: pathlib.Path = DEFAULT_DATASET_CSV) -> dict[str, Requirement]:
    """Return {Concept_ID: Requirement}, keyed exactly as the dataset's
    Concept_ID column (e.g. "CARD-014")."""
    requirements: dict[str, Requirement] = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            concept_id = row["Concept_ID"].strip()
            if not concept_id:
                continue
            requirement_class_raw = row["Requirement_class"].strip()
            try:
                requiredness = RequirementClass(requirement_class_raw)
            except ValueError:
                # Unrecognised class in the source data: fail loud rather
                # than silently defaulting a requirement's mandatoriness.
                raise ValueError(
                    f"{concept_id}: unknown Requirement_class "
                    f"{requirement_class_raw!r} in {csv_path}"
                ) from None
            requirements[concept_id] = Requirement(
                requirement_id=concept_id,
                activation_rule=row["Trigger"].strip(),
                requiredness=requiredness,
            )
    return requirements


@lru_cache(maxsize=1)
def default_requirements() -> dict[str, Requirement]:
    """Cached load of the default (repo-bundled) Clinical Dataset export."""
    return load_requirements()


def load_concept_labels(csv_path: pathlib.Path = DEFAULT_DATASET_CSV) -> dict[str, dict[str, str]]:
    """Return {Concept_ID: {"domain", "concept", "patient_question",
    "clinical_definition", "response_type"}}.

    Display metadata only -- not part of the canonical Requirement object
    (periop_core.models.Requirement), which stays limited to what the gap
    engine actually needs. This exists for API/UI concept pickers.
    """
    labels: dict[str, dict[str, str]] = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            concept_id = row["Concept_ID"].strip()
            if not concept_id:
                continue
            labels[concept_id] = {
                "domain": row["Domain"].strip(),
                "concept": row["Concept"].strip(),
                "patient_question": row["Patient_question"].strip(),
                "clinical_definition": row["Clinical_definition"].strip(),
                "response_type": row["Response_type"].strip(),
            }
    return labels


@lru_cache(maxsize=1)
def default_concept_labels() -> dict[str, dict[str, str]]:
    return load_concept_labels()
