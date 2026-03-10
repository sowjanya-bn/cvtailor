from __future__ import annotations

import json

from google import genai
from google.genai import types

from cvtailor.config import GEMINI_API_KEY, GEMINI_MODEL
from cvtailor.models import TailorRequest, TailorResult


client = genai.Client(api_key=GEMINI_API_KEY)


SYSTEM_PROMPT = """
You are CVTailor, a careful CV tailoring assistant.

Your job is to suggest minimal changes only.

Rules:
- Do NOT rewrite the whole CV
- Do NOT invent experience
- Be truthful and conservative
- Focus on professional CV standards used in UK, Europe, and India
- Prefer minimal edits to existing wording
- Return JSON only
"""


def analyze_cv_fit(req: TailorRequest) -> TailorResult:

    prompt = f"""
{SYSTEM_PROMPT}

Target region:
{req.target_region}

Job description:
{req.job_description}

Master CV:
{req.cv_text}

Return ONLY valid JSON in this schema:

{{
  "fit_summary": "string",
  "missing_keywords": ["string"],
  "suggestions": ["string"],
  "revised_summary": "string"
}}
"""

    config = types.GenerateContentConfig(
        temperature=0.0
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,   # gemini-3.1-flash-lite
        contents=prompt,
        config=config
    )

    content = response.text.strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError(f"Gemini output was not valid JSON:\n{content}")

    return TailorResult.model_validate(data)