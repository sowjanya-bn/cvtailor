from __future__ import annotations

from cvtailor.models import TailorRequest, TailorResult


def build_initial_context(req: TailorRequest, result: TailorResult) -> dict:
    return {
        "person": {
            "full_name": "Your Name",
            "location": "City, Country",
            "email": "your.email@example.com",
            "phone": "+44 0000 000000",
        },
        "headline": "Tailored CV",
        "summary": result.revised_summary,
        "skills": [
            {"name": "Core Skills", "items": ["Python", "Data Analysis", "LLMs"]}
        ],
        "experience": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "interests": [],
        "job_title": "Target Role",
        "job_keywords": result.missing_keywords,
        "target_region": req.target_region,
    }