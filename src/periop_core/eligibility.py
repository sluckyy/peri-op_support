"""Intake eligibility check -- new in the v1.1 addendum (gap #2), not
present in Full Spec v1.0. See docs/addenda/v1.1-gap-remediation.md.

Implements the new Table 23 step 1.5: evaluate age/procedure-urgency/
population-flag eligibility from the booking/referral feed, falling back
to patient self-declaration where the feed lacks a field, and hard-block
on any mismatch (booking feed is treated as authoritative for procedure
context, consistent with the existing FHIR-003/CF-009 pattern).
"""
from __future__ import annotations

from dataclasses import dataclass

from periop_core.enums import EligibilityResult

MINIMUM_AGE_YEARS = 18


@dataclass
class EligibilityContext:
    """Fields sourced from the booking/referral feed where available,
    else from patient self-declaration (each field independently)."""

    age_years: int | None
    age_source: str  # "booking_feed" | "self_declared"
    is_obstetric_procedure: bool | None
    is_obstetric_source: str
    is_emergency_listing: bool | None
    is_emergency_source: str


@dataclass
class EligibilityDecision:
    result: EligibilityResult
    reasons: list[str]


def evaluate_eligibility(ctx: EligibilityContext) -> EligibilityDecision:
    reasons: list[str] = []

    if ctx.age_years is None:
        reasons.append("Age could not be determined from booking feed or self-declaration")
    elif ctx.age_years < MINIMUM_AGE_YEARS:
        reasons.append(
            f"Age {ctx.age_years} is below the minimum scope of {MINIMUM_AGE_YEARS} "
            f"(source: {ctx.age_source})"
        )

    if ctx.is_obstetric_procedure:
        reasons.append(f"Obstetric procedure flagged (source: {ctx.is_obstetric_source})")

    if ctx.is_emergency_listing:
        reasons.append(f"Emergency listing flagged (source: {ctx.is_emergency_source})")

    if reasons:
        return EligibilityDecision(EligibilityResult.INELIGIBLE, reasons)
    return EligibilityDecision(EligibilityResult.ELIGIBLE, [])
