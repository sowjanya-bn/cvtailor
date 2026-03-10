from __future__ import annotations

import re
from pathlib import Path

import streamlit as st
import yaml

from cvtailor.models import TailorRequest
from cvtailor.tailoring import build_initial_context
from cvtailor.gemini_service import analyze_cv_fit
from cvtailor.pdf import render_latex_to_string, compile_latex_to_pdf


# ------------------------------
# Helpers
# ------------------------------

def load_base_cv_yaml(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Base CV YAML not found: {path}")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9\-\+/#\.]{1,}", (text or "").lower()))


def score_block(block: dict, jd_terms: set[str], title_keys: list[str]) -> float:
    parts = []

    for key in title_keys:
        value = block.get(key)
        if isinstance(value, str):
            parts.append(value)

    for bullet in block.get("bullets", []):
        if isinstance(bullet, dict):
            parts.append(bullet.get("text", ""))
        elif isinstance(bullet, str):
            parts.append(bullet)

    text = " ".join(parts)
    block_terms = tokenize(text)
    if not block_terms:
        return 0.0

    overlap = jd_terms.intersection(block_terms)
    return float(len(overlap))


def auto_pick_experience(base_cv: dict, jd_text: str, top_k: int = 3) -> list[dict]:
    jd_terms = tokenize(jd_text)
    ranked = sorted(
        base_cv.get("experience", []),
        key=lambda b: score_block(b, jd_terms, ["role", "company", "location"]),
        reverse=True,
    )
    return ranked[:top_k]


def auto_pick_projects(base_cv: dict, jd_text: str, top_k: int = 2) -> list[dict]:
    jd_terms = tokenize(jd_text)
    ranked = sorted(
        base_cv.get("projects", []),
        key=lambda b: score_block(b, jd_terms, ["title"]),
        reverse=True,
    )
    return ranked[:top_k]


def auto_pick_skills(base_cv: dict, jd_text: str, top_k: int = 3) -> list[dict]:
    jd_terms = tokenize(jd_text)
    ranked = []

    for category in base_cv.get("skills", []):
        items = category.get("items", [])
        item_terms = tokenize(" ".join(items))
        overlap = jd_terms.intersection(item_terms)
        ranked.append((len(overlap), category))

    ranked.sort(key=lambda x: x[0], reverse=True)
    picked = [cat for _, cat in ranked[:top_k]]

    return picked if picked else base_cv.get("skills", [])


def base_cv_to_text_subset(
    base_cv: dict,
    selected_experience: list[dict],
    selected_projects: list[dict],
    selected_skills: list[dict],
) -> str:
    lines = []

    headline = base_cv.get("headline", "")
    summary = base_cv.get("summary", "")
    if headline:
        lines.append(f"Headline: {headline}")
    if summary:
        lines.append(f"Summary: {summary}")

    if selected_skills:
        lines.append("Skills:")
        for category in selected_skills:
            lines.append(f"- {category.get('name', 'Skills')}: {', '.join(category.get('items', []))}")

    if selected_experience:
        lines.append("Experience:")
        for exp in selected_experience:
            role = exp.get("role", "")
            company = exp.get("company", "")
            lines.append(f"- {role} @ {company}")
            for bullet in exp.get("bullets", []):
                text = bullet.get("text", "") if isinstance(bullet, dict) else str(bullet)
                lines.append(f"  - {text}")

    if selected_projects:
        lines.append("Projects:")
        for proj in selected_projects:
            title = proj.get("title", "")
            lines.append(f"- {title}")
            for bullet in proj.get("bullets", []):
                text = bullet.get("text", "") if isinstance(bullet, dict) else str(bullet)
                lines.append(f"  - {text}")

    return "\n".join(lines)


def build_context_from_base_cv(
    base_cv: dict,
    selected_experience: list[dict],
    selected_projects: list[dict],
    selected_skills: list[dict],
    target_region: str,
    revised_summary: str | None = None,
) -> dict:
    return {
        "person": base_cv.get("person", {}),
        "headline": base_cv.get("headline", "Tailored CV"),
        "summary": revised_summary or base_cv.get("summary", ""),
        "skills": selected_skills,
        "experience": selected_experience,
        "projects": selected_projects,
        "education": base_cv.get("education", []),
        "certifications": base_cv.get("certifications", []),
        "interests": base_cv.get("interests", []),
        "job_title": "Target Role",
        "job_keywords": [],
        "target_region": target_region,
    }


def option_label_experience(item: dict) -> str:
    role = item.get("role", "")
    company = item.get("company", "")
    start = item.get("start", "")
    end = item.get("end", "")
    dates = f" ({start}–{end})" if start or end else ""
    return f"{role} @ {company}{dates}"


def option_label_project(item: dict) -> str:
    return item.get("title", "Untitled Project")


def option_label_skill(item: dict) -> str:
    return item.get("name", "Skills")


# ------------------------------
# Streamlit app
# ------------------------------

st.set_page_config(page_title="CVTailor", layout="wide")
st.title("CVTailor")
st.caption("Maximise fit. Minimise change.")

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "render_context" not in st.session_state:
    st.session_state.render_context = None

if "selected_exp" not in st.session_state:
    st.session_state.selected_exp = []

if "selected_proj" not in st.session_state:
    st.session_state.selected_proj = []

if "selected_skills" not in st.session_state:
    st.session_state.selected_skills = []

if "base_cv" not in st.session_state:
    st.session_state.base_cv = None

with st.sidebar:
    st.header("Settings")

    base_cv_path = st.text_input(
        "Base CV YAML path",
        value="data/cv/base_cv.yaml",
    )

    template_path = st.text_input(
        "LaTeX template",
        value="templates/cv.tex.j2",
    )

    output_dir = st.text_input(
        "Output directory",
        value="outputs",
    )

    region = st.selectbox(
        "Target CV region",
        ["uk", "europe", "india"],
        index=0,
    )

    auto_exp_k = st.slider("Auto-pick experience blocks", 1, 6, 3)
    auto_proj_k = st.slider("Auto-pick project blocks", 1, 6, 2)
    auto_skill_k = st.slider("Auto-pick skill categories", 1, 6, 3)

    st.divider()
    st.caption("The app auto-picks relevant blocks from the base CV, then lets you edit them.")

left, right = st.columns(2)

with left:
    st.subheader("Job description")
    jd_text = st.text_area(
        "Paste the job description",
        height=360,
        placeholder="Paste the job description here...",
    )

with right:
    st.subheader("Base CV")
    try:
        base_cv = load_base_cv_yaml(base_cv_path)
        st.session_state.base_cv = base_cv
        person = base_cv.get("person", {})
        st.success(f"Loaded base CV: {person.get('full_name', 'Unknown')}")
        st.json(
            {
                "headline": base_cv.get("headline", ""),
                "experience_blocks": len(base_cv.get("experience", [])),
                "project_blocks": len(base_cv.get("projects", [])),
                "skill_categories": len(base_cv.get("skills", [])),
            }
        )
    except Exception as e:
        st.error(str(e))
        st.stop()

analyze_clicked = st.button(
    "Auto-pick and analyze",
    type="primary",
    use_container_width=True,
)

if analyze_clicked:
    if not jd_text.strip():
        st.warning("Please paste the job description.")
        st.stop()

    base_cv = st.session_state.base_cv

    selected_exp = auto_pick_experience(base_cv, jd_text, auto_exp_k)
    selected_proj = auto_pick_projects(base_cv, jd_text, auto_proj_k)
    selected_skills = auto_pick_skills(base_cv, jd_text, auto_skill_k)

    st.session_state.selected_exp = selected_exp
    st.session_state.selected_proj = selected_proj
    st.session_state.selected_skills = selected_skills

    cv_subset_text = base_cv_to_text_subset(
        base_cv=base_cv,
        selected_experience=selected_exp,
        selected_projects=selected_proj,
        selected_skills=selected_skills,
    )

    request = TailorRequest(
        cv_text=cv_subset_text,
        job_description=jd_text,
        target_region=region,
    )

    with st.spinner("Analyzing selected CV subset with Gemini..."):
        result = analyze_cv_fit(request)

    context = build_context_from_base_cv(
        base_cv=base_cv,
        selected_experience=selected_exp,
        selected_projects=selected_proj,
        selected_skills=selected_skills,
        target_region=region,
        revised_summary=result.revised_summary,
    )
    context["job_keywords"] = result.missing_keywords

    st.session_state.analysis_result = result
    st.session_state.render_context = context

result = st.session_state.analysis_result
context = st.session_state.render_context
base_cv = st.session_state.base_cv

if result and context:
    st.divider()
    st.subheader("Auto-selected CV blocks")

    exp_options = base_cv.get("experience", [])
    proj_options = base_cv.get("projects", [])
    skill_options = base_cv.get("skills", [])

    exp_ids_default = [x.get("id") for x in st.session_state.selected_exp]
    proj_ids_default = [x.get("id") for x in st.session_state.selected_proj]
    skill_names_default = [x.get("name") for x in st.session_state.selected_skills]

    selected_exp = st.multiselect(
        "Experience",
        options=exp_options,
        default=[x for x in exp_options if x.get("id") in exp_ids_default],
        format_func=option_label_experience,
    )

    selected_proj = st.multiselect(
        "Projects",
        options=proj_options,
        default=[x for x in proj_options if x.get("id") in proj_ids_default],
        format_func=option_label_project,
    )

    selected_skills = st.multiselect(
        "Skill categories",
        options=skill_options,
        default=[x for x in skill_options if x.get("name") in skill_names_default],
        format_func=option_label_skill,
    )

    st.divider()

    info_col, keyword_col = st.columns(2)

    with info_col:
        st.subheader("Fit summary")
        st.write(result.fit_summary)

    with keyword_col:
        st.subheader("Missing keywords")
        if result.missing_keywords:
            for kw in result.missing_keywords:
                st.write(f"- {kw}")
        else:
            st.write("No obvious missing keywords found.")

    st.subheader("Tailoring suggestions")
    if result.suggestions:
        for i, suggestion in enumerate(result.suggestions, start=1):
            st.write(f"{i}. {suggestion}")
    else:
        st.write("No additional suggestions returned.")

    st.divider()
    st.subheader("Editable CV details")

    edit_col1, edit_col2 = st.columns(2)

    with edit_col1:
        full_name = st.text_input(
            "Full name",
            value=context["person"].get("full_name", ""),
        )
        location = st.text_input(
            "Location",
            value=context["person"].get("location", ""),
        )
        email = st.text_input(
            "Email",
            value=context["person"].get("email", ""),
        )

    with edit_col2:
        phone = st.text_input(
            "Phone",
            value=context["person"].get("phone", ""),
        )
        headline = st.text_input(
            "Headline",
            value=context.get("headline", ""),
        )
        job_title = st.text_input(
            "Target role title",
            value=context.get("job_title", "Target Role"),
        )

    summary = st.text_area(
        "Professional summary",
        value=context.get("summary", ""),
        height=180,
    )

    keywords_text = st.text_area(
        "Job keywords",
        value=", ".join(result.missing_keywords),
        height=100,
    )

    context = build_context_from_base_cv(
        base_cv=base_cv,
        selected_experience=selected_exp,
        selected_projects=selected_proj,
        selected_skills=selected_skills,
        target_region=region,
        revised_summary=summary,
    )

    context["person"]["full_name"] = full_name
    context["person"]["location"] = location
    context["person"]["email"] = email
    context["person"]["phone"] = phone
    context["headline"] = headline
    context["job_title"] = job_title
    context["job_keywords"] = [x.strip() for x in keywords_text.split(",") if x.strip()]

    st.session_state.render_context = context
    st.session_state.selected_exp = selected_exp
    st.session_state.selected_proj = selected_proj
    st.session_state.selected_skills = selected_skills

    st.divider()
    st.subheader("LaTeX preview")

    tex_preview = render_latex_to_string(template_path, context)
    st.code(tex_preview, language="tex")

    if st.button("Generate PDF", use_container_width=True):
        pdf_path = compile_latex_to_pdf(
            template_path=template_path,
            context=context,
            output_dir=output_dir,
        )

        st.success(f"PDF generated: {pdf_path}")

        with open(pdf_path, "rb") as f:
            st.download_button(
                label="Download PDF",
                data=f,
                file_name="cvtailor_cv.pdf",
                mime="application/pdf",
            )
else:
    st.info("Load a base CV YAML, paste a job description, then click Auto-pick and analyze.")