"""
Local datasheet / spec-sheet extraction.

Turns a vendor datasheet (PDF, CSV, XLSX or plain text) into raw text + tables
that a local LLM can read to extract component parameters. All parsing is local
(no network), so it is safe for air-gapped environments.

The mapping from extracted text to GNPy schema fields is done by the agent
(via the build/validate tools), NOT here - this module only surfaces content.
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    from langchain_core.tools import tool
except ImportError as exc:  # pragma: no cover - environment dependent
    raise ImportError(
        "langchain-core is not installed. Run `pip install -r requirements-agent.txt`."
    ) from exc

# Cap how much text we hand to the model to protect the context window.
MAX_CHARS = 20000


def _extract_pdf(path: Path) -> str:
    """Extract text (and simple tables) from a PDF using pdfplumber, falling
    back to pypdf if needed."""
    try:
        import pdfplumber

        parts: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages):
                parts.append(f"\n--- page {i + 1} ---")
                text = page.extract_text() or ""
                parts.append(text)
                for table in page.extract_tables() or []:
                    rows = [
                        " | ".join("" if c is None else str(c) for c in row)
                        for row in table
                    ]
                    if rows:
                        parts.append("[table]\n" + "\n".join(rows))
        return "\n".join(parts)
    except ImportError:
        pass

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except ImportError as exc:
        raise ImportError(
            "No PDF parser available. Install pdfplumber or pypdf "
            "(see requirements-agent.txt)."
        ) from exc


def _extract_tabular(path: Path) -> str:
    """Extract CSV/XLSX content as readable text via pandas."""
    import pandas as pd

    if path.suffix.lower() in (".xlsx", ".xls"):
        sheets = pd.read_excel(path, sheet_name=None)
        parts = []
        for name, df in sheets.items():
            parts.append(f"\n--- sheet: {name} ---")
            parts.append(df.to_csv(index=False))
        return "\n".join(parts)
    df = pd.read_csv(path)
    return df.to_csv(index=False)


def extract_text(path: str | Path) -> str:
    """Extract readable text from a datasheet file by extension."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf(p)
    elif suffix in (".csv", ".xlsx", ".xls"):
        text = _extract_tabular(p)
    elif suffix in (".txt", ".md", ".json"):
        text = p.read_text(encoding="utf-8", errors="replace")
    else:
        raise ValueError(
            f"Unsupported datasheet type '{suffix}'. Use pdf, csv, xlsx, txt or md."
        )
    text = text.strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n...[truncated]..."
    return text


@tool
def extract_datasheet(path: str) -> str:
    """Extract raw text and tables from a vendor datasheet so you can read its
    specifications and map them to a GNPy component.

    Supports .pdf, .csv, .xlsx, .txt and .md files. After reading, identify the
    component type (EDFA / fiber / transceiver / ROADM), convert units carefully
    (dB/km, Hz vs GHz, ps/nm vs s/m^2), then call describe_component_schema and
    preview_component to build a validated component for the user to approve.
    """
    try:
        text = extract_text(path)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": str(e)})
    return json.dumps({
        "path": path,
        "chars": len(text),
        "text": text,
        "reminder": ("Map values to schema keys via describe_component_schema; "
                     "convert units; then preview_component before saving."),
    })
