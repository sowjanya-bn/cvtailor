# CVTailor

CVTailor is a human-in-the-loop CV tailoring tool built with Streamlit.

Principle: maximise fit and minimise change.

## Features
- Paste a master CV
- Paste a job description
- Use Gemini to suggest minimal improvements
- Review suggestions in the UI
- Export LaTeX and PDF

## Requirements
- Python 3.10+
- A working LaTeX installation (`pdflatex`)
- Gemini API key

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Add your Gemini key:

```bash
GEMINI_API_KEY=your_key_here
```

Run the app:
```bash
streamlit run app.py
```

Notes

The current version keeps everything simple and editable.

Gemini is used only for minimal-change suggestions.

The PDF export renders a LaTeX template and compiles it with pdflatex.


Pre-requisites
```bash
brew install --cask basictex
sudo tlmgr install enumitem
sudo /Library/TeX/texbin/tlmgr install paracol tcolorbox titlesec hyperref xcolor enumitem geometry lmodern
sudo /Library/TeX/texbin/tlmgr install paracol
```