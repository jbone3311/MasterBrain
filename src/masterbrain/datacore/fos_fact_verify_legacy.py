"""Pure, isolated FOS fact-verifier compatibility functions.

Pinned donor: FOS-Master 218d5caec2f20b9047fd3eb8e027dc671acf0c15,
``_SYSTEM/tools/fact_verify.py`` SHA-256
c2f4c38c8a6bd783e726cebde1f555586d5675639aab2beb45c50128898feb8b.

This is *not* a MasterBrain evidence-attestation or financial-truth API. Filename
and sender heuristics are donor classifications only; numeric substring matches
are donor compatibility only. Do not use these results to publish claims.
"""

from __future__ import annotations

import re

T1, T2, T3 = "T1", "T2", "T3"
TIER_WEIGHT = {T1: 1.5, T2: 1.0, T3: 0.7, None: 0.5}

T1_PATTERNS = re.compile(
    r"subscription agmt|subscription agreement|joinder|lpagreement|lp agreement|"
    r"executed|signed|k-?1\b|424b4|form s-1|prospectus|amended and restated",
    re.I,
)
T2_PATTERNS = re.compile(
    r"portfolio summary|custodian report|investor statement|capitalcall|capital call|"
    r"period report|quarterly|pcap|financial-statement|financial statement|"
    r"stockdistribution|invoice|management fee",
    re.I,
)
ADMIN_EMAIL_DOMAINS = re.compile(r"getquid\.com|troycapitalpartners|dblpartners|tcp-", re.I)


def classify_tier(source_type: str | None, kind: str | None,
                  filename: str | None, from_party: str = "") -> str | None:
    """Return the donor's heuristic tier; never an attested source tier."""
    filename = filename or ""
    if source_type == "regulatory" or T1_PATTERNS.search(filename):
        return T1
    if source_type == "email":
        return T2 if ADMIN_EMAIL_DOMAINS.search(from_party or "") else T3
    if T2_PATTERNS.search(filename):
        return T2
    if source_type == "primary_document":
        return T2
    if source_type == "internal_correction":
        return None
    return T3


def value_variants(value: object) -> set[str]:
    """Return donor float/substring search variants, for comparison only."""
    variants = {str(value)}
    s = str(value).strip()
    try:
        num = float(s.replace(",", "").replace("$", ""))
        variants.add(f"{num:,.0f}")
        variants.add(f"{num:,.2f}")
        variants.add(f"{int(num)}")
        if num >= 1_000_000_000:
            variants.add(f"{num/1_000_000_000:g}B")
            variants.add(f"{num/1_000_000_000:g} billion")
        elif num >= 1_000_000:
            variants.add(f"{num/1_000_000:g}M")
            variants.add(f"{num/1_000_000:g} million")
        elif num >= 1_000:
            variants.add(f"{num/1_000:g}k")
            variants.add(f"{num/1_000:g}K")
    except ValueError:
        pass
    return variants


def confirmation_status(matches: list[bool | None]) -> str:
    """Replicate donor status precedence; missing/unreadable sources stay unknown."""
    if any(match is False for match in matches):
        return "DISPUTED"
    if any(match is True for match in matches):
        return "CONFIRMED"
    return "UNVERIFIED"
