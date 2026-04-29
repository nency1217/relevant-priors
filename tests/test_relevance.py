"""Smoke tests for the relevance logic.

Run with:
    python -m pytest tests/ -v

Or without pytest:
    python tests/test_relevance.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Case, Study  # noqa: E402
from relevance.parser import (  # noqa: E402
    extract_modality, extract_regions, regions_overlap,
)
from relevance.predictor import HybridPredictor  # noqa: E402


def test_extract_regions_brain():
    assert "brain" in extract_regions("MRI BRAIN STROKE LIMITED WITHOUT CONTRAST")


def test_extract_regions_chest():
    assert "chest" in extract_regions("CT CHEST WITH CONTRAST")


def test_extract_regions_multi():
    r = extract_regions("CT ABDOMEN AND PELVIS WITH IV CONTRAST")
    assert "abdomen" in r and "pelvis" in r


def test_extract_modality_cta():
    assert extract_modality("CTA CHEST PE PROTOCOL") == "CT"


def test_extract_modality_field_takes_priority():
    assert extract_modality("brain follow up", modality_field="MR") == "MRI"


def test_regions_overlap_same():
    assert regions_overlap({"chest"}, {"chest"})


def test_regions_overlap_adjacent():
    # Sacrum and pelvis are co-imaged, the labels treat them as relevant.
    # NOTE: lone abdomen <-> lone pelvis is NOT adjacent — labels mark only
    # 8% of those pairs as relevant. CT abd/pel still matches lone abdomen
    # or lone pelvis via direct overlap, not via this edge.
    assert regions_overlap({"sacrum"}, {"pelvis"}, allow_adjacent=True)
    assert not regions_overlap({"abdomen"}, {"pelvis"}, allow_adjacent=True)
    assert not regions_overlap({"chest"}, {"abdomen"}, allow_adjacent=True)


def test_regions_overlap_unrelated():
    assert not regions_overlap({"knee"}, {"brain"})


def _case(current_desc: str, prior_descs: list[str]) -> Case:
    return Case(
        case_id="c1",
        current_study=Study(study_id="cur", study_description=current_desc),
        prior_studies=[
            Study(study_id=f"p{i}", study_description=d)
            for i, d in enumerate(prior_descs)
        ],
    )


def test_predictor_chest_priors():
    p = HybridPredictor()
    case = _case(
        "CT CHEST WITH CONTRAST",
        ["CHEST X-RAY 2 VIEWS", "MRI KNEE LEFT", "ECHO 2D Mmode TTE"],
    )
    preds = {pr.study_id: pr.predicted_is_relevant for pr in p.predict_case(case)}
    assert preds["p0"] is True   # same region, different modality
    assert preds["p1"] is False  # totally different
    # CT chest <-> echo: labels treat this as not relevant ~62% of the time,
    # so the predictor (no cardiac<->chest adjacency) returns False.
    assert preds["p2"] is False


def test_predictor_xr_chest_vs_echo_not_relevant():
    """Chest XR and echo share the chest/cardiac edge but neither is
    cross-sectional, so the labels treat them as not relevant. Predictor
    should respect that."""
    p = HybridPredictor()
    case = _case("XR Chest 1V Frontal Only", ["ECHO 2D Mmode TTE"])
    preds = {pr.study_id: pr.predicted_is_relevant for pr in p.predict_case(case)}
    assert preds["p0"] is False


def test_predictor_brain_stroke():
    p = HybridPredictor()
    case = _case(
        "MRI BRAIN STROKE LIMITED WITHOUT CONTRAST",
        ["CT HEAD WITHOUT CONTRAST", "MRI L-SPINE", "XR HAND LEFT"],
    )
    preds = {pr.study_id: pr.predicted_is_relevant for pr in p.predict_case(case)}
    assert preds["p0"] is True
    assert preds["p1"] is False
    assert preds["p2"] is False


def test_predictor_mammo_modality_boost():
    p = HybridPredictor()
    case = _case(
        "DIAGNOSTIC MAMMOGRAM BILATERAL",
        ["SCREENING MAMMOGRAM BILATERAL"],
    )
    preds = {pr.study_id: pr.predicted_is_relevant for pr in p.predict_case(case)}
    assert preds["p0"] is True


def test_predictor_returns_one_per_prior():
    p = HybridPredictor()
    case = _case("CT CHEST", ["XR CHEST", "XR CHEST", "XR CHEST"])
    preds = p.predict_case(case)
    assert len(preds) == 3
    assert all(pr.case_id == "c1" for pr in preds)


if __name__ == "__main__":
    # Run all tests in this module without pytest.
    import inspect
    failed = 0
    tests = [
        (n, fn) for n, fn in globals().items()
        if n.startswith("test_") and inspect.isfunction(fn)
    ]
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {name}  {e!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
