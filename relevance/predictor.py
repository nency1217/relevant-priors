"""Core relevance predictor.

Decision rule (in order of preference):
  1. If both studies have parsed body regions, a prior is relevant when its
     regions overlap the current's regions (including anatomically adjacent
     regions like chest <-> upper abdomen).
  2. If region parsing fails for either side, fall back to a token-overlap
     similarity check on study descriptions.
  3. If everything fails, default to True. The accuracy metric counts skipped
     priors as incorrect, and clinical practice errs toward showing priors.

The predictor caches per-(current_desc, prior_desc) pairs because evaluator
calls often repeat similar pairs across cases.
"""
from typing import List, Optional, Tuple

from models import Case, Prediction, Study
from .parser import extract_modality, extract_regions, regions_overlap


# Tokens that carry no anatomic signal and should be ignored in fallback
# similarity. Kept short on purpose — over-aggressive stoplisting hurts.
_STOPWORDS = {
    "WITHOUT", "WITH", "WO", "W", "AND", "OR", "OF", "THE", "A", "AN",
    "CONTRAST", "IV", "PO", "LIMITED", "ROUTINE", "STUDY", "EXAM",
    "FOR", "TO", "PROTOCOL", "PT", "PATIENT",
}


class HybridPredictor:
    """Body-region + modality matcher with a token-overlap fallback."""

    def __init__(self) -> None:
        # cache: (current_desc, prior_desc) -> bool
        self._cache: dict[Tuple[str, str], bool] = {}

    # ---- public API -----------------------------------------------------

    def predict_case(self, case: Case) -> List[Prediction]:
        """Return one prediction per prior_study in the case."""
        current = case.current_study
        cur_text = self._study_text(current)
        cur_regions = extract_regions(current.study_description, current.body_part)
        cur_modality = extract_modality(current.study_description, current.modality)

        out: List[Prediction] = []
        for prior in case.prior_studies:
            relevant = self._predict_one(
                cur_text, cur_regions, cur_modality, prior,
            )
            out.append(Prediction(
                case_id=case.case_id,
                study_id=prior.study_id,
                predicted_is_relevant=bool(relevant),
            ))
        return out

    # ---- internals ------------------------------------------------------

    def _predict_one(self, cur_text: str, cur_regions, cur_modality,
                     prior: Study) -> bool:
        prior_text = self._study_text(prior)
        key = (cur_text, prior_text)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        prior_regions = extract_regions(prior.study_description, prior.body_part)
        prior_modality = extract_modality(prior.study_description, prior.modality)

        if cur_regions and prior_regions:
            result = regions_overlap(cur_regions, prior_regions, allow_adjacent=True)
            # cardiac <-> chest: 90% True when both sides are CT/MRI, but
            # only 3-34% True for other modality combos (echo vs chest XR,
            # NM perf vs chest XR, CT chest vs echo). Add adjacency only
            # when *both* modalities are cross-sectional.
            if not result and self._cardiac_chest_pair(cur_regions, prior_regions):
                if self._both_cross_sectional(cur_modality, prior_modality):
                    result = True
            # carotid <-> head/brain: only relevant when both descriptions
            # are CTAs (CT angiograms). Plain CT head + carotid US is
            # mostly not relevant per the labels.
            if not result and self._carotid_head_pair(cur_regions, prior_regions):
                if self._both_cta(cur_text, prior_text):
                    result = True
            # tspine <-> chest: 73% True when both sides are XR (the lateral
            # of a thoracic spine XR shows the chest). Other modality combos
            # are much lower (CT/MRI tspine vs CT/XR chest is ~25% True).
            if not result and self._tspine_chest_pair(cur_regions, prior_regions):
                if cur_modality == "XR" and prior_modality == "XR":
                    result = True
        else:
            # Region parsing failed for one side; fall back to token overlap.
            result = self._token_similarity(cur_text, prior_text)
            if result is None:
                # Last-resort default: show the prior. Skipping is penalized
                # the same as a wrong False, and most priors are at least
                # tangentially relevant in clinical practice.
                result = True

        # Modality boost: if regions overlap *and* modalities match exactly,
        # we're already returning True. If regions don't overlap but modalities
        # match (e.g. mammogram vs mammogram), tilt toward True.
        if not result and cur_modality and prior_modality and cur_modality == prior_modality:
            # Mammography priors are almost always relevant to a current mammo.
            # Same for DEXA serial follow-ups. For other modalities require
            # at least *some* region info before flipping.
            if cur_modality in {"MAMMO", "DEXA"}:
                result = True

        self._cache[key] = result
        return result

    @staticmethod
    def _study_text(s: Study) -> str:
        parts = [s.study_description or "", s.body_part or "", s.modality or ""]
        return " ".join(p for p in parts if p).upper()

    @staticmethod
    def _cardiac_chest_pair(a: set, b: set) -> bool:
        """True if one side is cardiac-only and the other is chest-like.
        Used to gate the modality-aware cardiac<->chest rule."""
        chest_like = {"chest", "vascular_chest", "ribs"}
        if "cardiac" in a and (b & chest_like) and "cardiac" not in b:
            return True
        if "cardiac" in b and (a & chest_like) and "cardiac" not in a:
            return True
        return False

    @staticmethod
    def _both_cross_sectional(a: str | None, b: str | None) -> bool:
        """True only if BOTH modalities are CT or MRI. The label data
        shows cardiac<->chest is 90% relevant for CT-CT pairs but
        <40% for any other combo."""
        cs = {"CT", "MRI"}
        return (a in cs) and (b in cs)

    @staticmethod
    def _carotid_head_pair(a: set, b: set) -> bool:
        """True if one side is carotid-only and the other is head/brain."""
        head_like = {"head", "brain"}
        if "carotid" in a and (b & head_like) and "carotid" not in b:
            return True
        if "carotid" in b and (a & head_like) and "carotid" not in a:
            return True
        return False

    @staticmethod
    def _both_cta(a: str, b: str) -> bool:
        """True if both descriptions look like CT angiograms.
        CTA carotid <-> CTA head is 87% relevant; plain CT head <-> carotid
        US (or even MRI) is much less."""
        markers = ("CTA", "ANGIO", "ANGIOGRAM", "ANGIOGRAPHY")
        au, bu = a.upper(), b.upper()
        return any(m in au for m in markers) and any(m in bu for m in markers)

    @staticmethod
    def _tspine_chest_pair(a: set, b: set) -> bool:
        """True if one side is tspine-only and the other is chest-only."""
        if a == {"tspine"} and b == {"chest"}:
            return True
        if b == {"tspine"} and a == {"chest"}:
            return True
        return False

    @classmethod
    def _token_similarity(cls, a: str, b: str) -> Optional[bool]:
        if not a or not b:
            return None
        ta = {t for t in a.split() if t and t not in _STOPWORDS}
        tb = {t for t in b.split() if t and t not in _STOPWORDS}
        if not ta or not tb:
            return None
        denom = min(len(ta), len(tb))
        overlap = len(ta & tb) / denom if denom else 0.0
        return overlap >= 0.4
