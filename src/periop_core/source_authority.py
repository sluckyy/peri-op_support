"""Loads the Source Authority Matrix (docs/exports/source_authority_matrix.csv)
and exposes it as a lookup used by the reconciliation engine's "assess
source fitness" step (Reconciliation Algorithm, step 4).

Core principle (§4.5 / Reconciliation Algorithm step 4): there is no single
global source hierarchy. A patient is often authoritative for current
symptoms and actual medicine use; a diagnostic result system is
authoritative for a measured result; a medication order is evidence of an
order, not proof of ingestion. Fitness is evaluated per datatype.
"""
from __future__ import annotations

import csv
import pathlib
from dataclasses import dataclass
from functools import lru_cache

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DEFAULT_MATRIX_CSV = REPO_ROOT / "docs" / "exports" / "source_authority_matrix.csv"


@dataclass(frozen=True)
class SourceAuthorityRule:
    data_type: str
    preferred_sources: str
    patient_proxy_role: str
    potential_conflicts: str
    reconciliation_principle: str
    freshness_consideration: str
    auto_resolution_raw: str

    @property
    def allows_auto_resolution(self) -> bool:
        """Conservative parse of the free-text 'Auto-resolution?' column.

        Anything starting with "No" is treated as not auto-resolvable.
        Everything else ("Yes", "Usually", "Often if coherent", ...) is
        treated as *potentially* auto-resolvable by the caller, which must
        still apply its own materiality check (Reconciliation Algorithm
        step 6) before actually auto-resolving — this property alone is
        not a green light.
        """
        return not self.auto_resolution_raw.strip().lower().startswith("no")


def load_source_authority_matrix(
    csv_path: pathlib.Path = DEFAULT_MATRIX_CSV,
) -> dict[str, SourceAuthorityRule]:
    """Return {Data type: SourceAuthorityRule}, keyed exactly on the
    matrix's 'Data type' column text."""
    rules: dict[str, SourceAuthorityRule] = {}
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data_type = row["Data type"].strip()
            if not data_type:
                continue
            rules[data_type] = SourceAuthorityRule(
                data_type=data_type,
                preferred_sources=row["Preferred/strong sources"].strip(),
                patient_proxy_role=row["Patient/proxy role"].strip(),
                potential_conflicts=row["Potential conflicts"].strip(),
                reconciliation_principle=row["Default reconciliation principle"].strip(),
                freshness_consideration=row["Freshness consideration"].strip(),
                auto_resolution_raw=row["Auto-resolution?"].strip(),
            )
    return rules


@lru_cache(maxsize=1)
def default_source_authority_matrix() -> dict[str, SourceAuthorityRule]:
    return load_source_authority_matrix()
