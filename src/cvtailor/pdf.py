from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def escape_latex(value) -> str:
    if value is None:
        return ""
    value = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


def render_latex_to_string(template_path: str, context: dict) -> str:
    template_file = Path(template_path)
    env = Environment(loader=FileSystemLoader(str(template_file.parent)))
    env.filters["latex_escape"] = escape_latex
    template = env.get_template(template_file.name)
    return template.render(**context)


def compile_latex_to_pdf(template_path: str, context: dict, output_dir: str) -> Path:
    if not shutil.which("pdflatex"):
        raise RuntimeError("pdflatex not found. Install BasicTeX or MacTeX and ensure it is in PATH.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    tex_str = render_latex_to_string(template_path, context)
    tex_file = output_path / "cv.tex"
    tex_file.write_text(tex_str, encoding="utf-8")

    result = subprocess.run(
        [
            "pdflatex",
            "-interaction=nonstopmode",
            "-output-directory",
            str(output_path),
            str(tex_file),
        ],
        capture_output=True,
        text=True,
    )

    pdf_file = output_path / "cv.pdf"

    # If PDF exists, accept success even if pdflatex returned non-zero.
    if pdf_file.exists():
        return pdf_file

    log_file = output_path / "cv.log"
    log_text = log_file.read_text(encoding="utf-8", errors="ignore") if log_file.exists() else ""

    raise RuntimeError(
        "LaTeX compilation failed.\n\n"
        f"STDOUT:\n{result.stdout}\n\n"
        f"STDERR:\n{result.stderr}\n\n"
        f"LOG:\n{log_text[-4000:]}"
    )