"""Parse free-text radiology study descriptions into structured features.

Two extractors:
  - extract_regions: returns the set of canonical body regions present
  - extract_modality: returns the canonical modality (MRI/CT/XR/...)

Both are pure functions and cheap. We pad the description with spaces on
each side so word-boundary matches like " CT " or " ABD " work without
regex overhead.
"""
from typing import Optional, Set

from .taxonomy import ADJACENT_REGIONS, MODALITY_KEYWORDS, REGION_KEYWORDS


def _norm(text: Optional[str]) -> str:
    if not text:
        return ""
    return f" {text.upper().strip()} "


def extract_regions(description: Optional[str],
                    body_part: Optional[str] = None) -> Set[str]:
    """Return canonical body regions present in the description.

    body_part is an optional structured field that some datasets supply
    alongside the description. When present we fold it into the search text.

    Post-processing: when a specific region is matched, its generic parent
    is suppressed. For example "cervical spine" matches both `cspine` and
    bare `spine` — but if we keep both, two unrelated spine segments end
    up overlapping on `spine`. Strip the generic when a specific is present.
    """
    text = _norm(description) + _norm(body_part)
    if not text.strip():
        return set()
    found: Set[str] = set()
    for region, keywords in REGION_KEYWORDS.items():
        for kw in keywords:
            if kw.upper() in text:
                found.add(region)
                break

    # Suppress generic regions when more specific ones are present.
    if found & {"cspine", "tspine", "lspine", "sacrum"}:
        found.discard("spine")
    if found & {"brain", "face", "sinus", "orbit", "iac", "pituitary", "tmj"}:
        found.discard("head")
    # DEXA bone-density studies often contain "Hip/Spine" in the
    # description and would otherwise match those anatomic regions, but
    # the labels treat DEXA as its own modality unrelated to structural
    # spine/hip imaging. Strip those when dexa is matched.
    if "dexa" in found:
        for region in ("spine", "hip", "lspine", "femur", "tspine",
                       "lower_extremity_generic"):
            found.discard(region)

    return found


def extract_modality(description: Optional[str],
                     modality_field: Optional[str] = None) -> Optional[str]:
    """Return canonical modality, preferring an explicit modality field."""
    if modality_field:
        m = modality_field.upper().strip()
        # Direct mappings for common DICOM modality codes
        direct = {
            "MR": "MRI", "MRI": "MRI",
            "CT": "CT", "CTA": "CT",
            "CR": "XR", "DX": "XR", "XR": "XR", "RF": "FLUORO",
            "US": "US",
            "MG": "MAMMO", "MAMMO": "MAMMO",
            "PT": "PET", "PET": "PET",
            "NM": "NM",
            "BMD": "DEXA", "DEXA": "DEXA",
        }
        if m in direct:
            return direct[m]
    text = _norm(description)
    if not text.strip():
        return None
    for modality, keywords in MODALITY_KEYWORDS.items():
        for kw in keywords:
            if kw.upper() in text:
                return modality
    return None


def regions_overlap(a: Set[str], b: Set[str], allow_adjacent: bool = True) -> bool:
    """Return True if region sets share an element, optionally allowing
    anatomically adjacent regions to count as overlap.

    Adjacency is checked symmetrically — both `a`'s adjacents against `b`
    AND `b`'s adjacents against `a`. This matters for one-way mappings
    like PET/wholebody → all regions, where the "all regions" side is
    encoded only on the PET key.
    """
    if not a or not b:
        return False
    if a & b:
        return True
    if not allow_adjacent:
        return False
    for region in a:
        neighbors = ADJACENT_REGIONS.get(region)
        if neighbors and neighbors & b:
            return True
    for region in b:
        neighbors = ADJACENT_REGIONS.get(region)
        if neighbors and neighbors & a:
            return True
    return False
