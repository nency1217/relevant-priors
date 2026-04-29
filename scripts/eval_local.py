"""Run the predictor against a local labeled JSON file (the public eval split).

Usage:
    python -m scripts.eval_local path/to/public_eval.json

The labeled JSON is expected to follow the challenge request schema with one
extra field per prior: `is_relevant` (bool ground truth).

Prints overall accuracy plus a confusion matrix and a sample of mistakes
to help you tune the taxonomy. Skipped predictions count as incorrect, but
this script always returns a prediction per prior so that's a non-issue here.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# Allow `python -m scripts.eval_local` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Case, PredictRequest, Study  # noqa: E402
from relevance import HybridPredictor  # noqa: E402


def load_eval(path: str):
    """Load the public eval JSON.

    Two supported formats:
    1. Truth embedded per-prior under `is_relevant`.
    2. Truth in a separate top-level `truth` array, with entries keyed by
       (case_id, study_id) and labeled `is_relevant_to_current`. This is the
       format New Lantern actually ships.
    """
    with open(path, "r") as f:
        data = json.load(f)

    truth: dict[tuple[str, str], bool] = {}

    # Format 2: separate truth array.
    for entry in data.get("truth", []):
        key = (str(entry["case_id"]), str(entry["study_id"]))
        # Field name varies between formats.
        if "is_relevant_to_current" in entry:
            truth[key] = bool(entry["is_relevant_to_current"])
        elif "is_relevant" in entry:
            truth[key] = bool(entry["is_relevant"])

    cases = []
    for raw_case in data["cases"]:
        priors_clean = []
        for p in raw_case.get("prior_studies", []):
            study_id = str(p["study_id"])
            # Format 1: pull truth out of priors if present.
            if "is_relevant" in p:
                truth[(str(raw_case["case_id"]), study_id)] = bool(p["is_relevant"])
            priors_clean.append({k: v for k, v in p.items() if k != "is_relevant"})
        case_clean = {**raw_case, "prior_studies": priors_clean}
        cases.append(case_clean)

    req = PredictRequest(cases=[Case(**c) for c in cases])
    return req, truth


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m scripts.eval_local <public_eval.json>")
        return 2
    path = sys.argv[1]
    print(f"loading {path} ...")
    req, truth = load_eval(path)
    print(f"  {len(req.cases)} cases, {len(truth)} labeled priors")

    predictor = HybridPredictor()
    correct = 0
    total = 0
    confusion = Counter()
    mistakes = []

    for case in req.cases:
        for pred in predictor.predict_case(case):
            key = (str(pred.case_id), str(pred.study_id))
            if key not in truth:
                continue
            actual = truth[key]
            predicted = pred.predicted_is_relevant
            total += 1
            if predicted == actual:
                correct += 1
            else:
                # Find the studies for context
                cur = case.current_study
                prior_match = next(
                    (p for p in case.prior_studies if p.study_id == pred.study_id),
                    None,
                )
                mistakes.append({
                    "case_id": case.case_id,
                    "current": cur.study_description,
                    "prior": prior_match.study_description if prior_match else None,
                    "predicted": predicted,
                    "actual": actual,
                })
            label_pair = (
                "T" if actual else "F",
                "T" if predicted else "F",
            )
            confusion[label_pair] += 1

    acc = correct / total if total else 0.0
    print()
    print(f"accuracy: {acc:.4f}  ({correct}/{total})")
    print("confusion matrix (actual, predicted):")
    for actual_label in ("T", "F"):
        for pred_label in ("T", "F"):
            print(f"  actual={actual_label} predicted={pred_label}: "
                  f"{confusion[(actual_label, pred_label)]}")

    print()
    print("first 15 mistakes:")
    for m in mistakes[:15]:
        marker = "FN" if m["actual"] and not m["predicted"] else "FP"
        print(f"  [{marker}] case={m['case_id']}")
        print(f"        current: {m['current']}")
        print(f"        prior:   {m['prior']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
