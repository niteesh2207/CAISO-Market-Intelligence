from __future__ import annotations

from market_intelligence.quality.models import (
    ClaimRequirement,
    ClaimType,
)


DEFAULT_REQUIREMENTS: dict[
    ClaimType,
    ClaimRequirement,
] = {
    ClaimType.OBSERVED_FACT: ClaimRequirement(
        claim_type=ClaimType.OBSERVED_FACT,
        requires_primary_source=True,
        requires_cross_check=False,
        requires_observation_time=False,
        minimum_records=1,
    ),
    ClaimType.NUMERIC_FACT: ClaimRequirement(
        claim_type=ClaimType.NUMERIC_FACT,
        requires_primary_source=True,
        requires_cross_check=False,
        requires_observation_time=True,
        requires_unit=True,
        requires_market_context=True,
        requires_timezone=True,
        minimum_records=1,
    ),
    ClaimType.CALCULATION: ClaimRequirement(
        claim_type=ClaimType.CALCULATION,
        requires_primary_source=True,
        requires_cross_check=False,
        requires_observation_time=True,
        requires_unit=True,
        requires_market_context=True,
        requires_timezone=True,
        minimum_records=1,
    ),
    ClaimType.EXPLANATION: ClaimRequirement(
        claim_type=ClaimType.EXPLANATION,
        requires_primary_source=True,
        requires_cross_check=True,
        minimum_records=2,
    ),
    ClaimType.ANALYST_INFERENCE: ClaimRequirement(
        claim_type=ClaimType.ANALYST_INFERENCE,
        requires_primary_source=True,
        requires_cross_check=True,
        minimum_records=2,
    ),
    ClaimType.FORECAST: ClaimRequirement(
        claim_type=ClaimType.FORECAST,
        requires_primary_source=True,
        requires_cross_check=True,
        requires_observation_time=True,
        minimum_records=2,
    ),
}


def requirement_for(
    claim_type: ClaimType,
) -> ClaimRequirement:
    return DEFAULT_REQUIREMENTS[claim_type]
