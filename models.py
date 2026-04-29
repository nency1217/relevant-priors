"""Pydantic models matching the challenge request/response schema.

Schema is permissive on input (extra fields ignored, optional fields tolerated)
because real radiology data is messy. Output is strict per the contract:
each prior must come back with case_id, study_id, predicted_is_relevant.
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class Study(BaseModel):
    """A radiology study. Only study_id is strictly required."""
    model_config = ConfigDict(extra="ignore")

    study_id: str
    study_description: Optional[str] = None
    study_date: Optional[str] = None
    modality: Optional[str] = None
    body_part: Optional[str] = None


class Case(BaseModel):
    """One patient case: a current exam plus their prior exams."""
    model_config = ConfigDict(extra="ignore")

    case_id: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    current_study: Study
    prior_studies: List[Study] = []


class PredictRequest(BaseModel):
    """Top-level request. Extra envelope fields (challenge_id, schema_version,
    generated_at) are accepted but not required for prediction."""
    model_config = ConfigDict(extra="ignore")

    challenge_id: Optional[str] = None
    schema_version: Optional[int] = None
    generated_at: Optional[str] = None
    cases: List[Case]


class Prediction(BaseModel):
    case_id: str
    study_id: str
    predicted_is_relevant: bool


class PredictResponse(BaseModel):
    predictions: List[Prediction]
