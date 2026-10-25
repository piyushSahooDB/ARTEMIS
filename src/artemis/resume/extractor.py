"""Resume parsing and evidence extraction engine.

Extracts verifiable qualifications, projects, skills, and coursework from
PDF, plain-text, and Markdown résumés into structured ResumeEvidence models.
Preserves exact source text snippets and marks all extractions as UNVERIFIED
until reviewed by the student.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Sequence, Union

from artemis.models.common import VerificationStatus
from artemis.models.resume import EvidenceCategory, ResumeEvidence

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    pypdf = None  # type: ignore[assignment]
    PYPDF_AVAILABLE = False


COMMON_TECH_SKILLS = [
    "Python", "C++", "C", "Java", "Go", "Rust", "JavaScript", "TypeScript", "SQL",
    "PyTorch", "TensorFlow", "JAX", "Keras", "Scikit-Learn", "NumPy", "Pandas",
    "Linux", "Docker", "Kubernetes", "Git", "PostgreSQL", "SQLite", "Redis",
    "Distributed Systems", "Raft", "Paxos", "Consensus", "Formal Verification",
    "Cryptography", "Operating Systems", "Compilers", "Computer Networks",
    "Computer Architecture", "Algorithms", "Data Structures", "Machine Learning",
    "Deep Learning", "Natural Language Processing", "Computer Vision",
]

SECTION_PATTERNS: list[tuple[EvidenceCategory, re.Pattern[str]]] = [
    (
        EvidenceCategory.RESEARCH_EXPERIENCE,
        re.compile(r"^(?:#+\s*)?(?:research(?:\s+experience|\s+projects?)?|academic\s+research)\b[:\s]*$", re.IGNORECASE),
    ),
    (
        EvidenceCategory.PROJECT,
        re.compile(r"^(?:#+\s*)?(?:projects?|technical\s+projects?|course\s+projects?|key\s+projects?)\b[:\s]*$", re.IGNORECASE),
    ),
    (
        EvidenceCategory.WORK_EXPERIENCE,
        re.compile(r"^(?:#+\s*)?(?:work\s+experience|professional\s+experience|experience|employment|internships?)\b[:\s]*$", re.IGNORECASE),
    ),
    (
        EvidenceCategory.PUBLICATION,
        re.compile(r"^(?:#+\s*)?(?:publications?|preprints?|conference\s+papers?)\b[:\s]*$", re.IGNORECASE),
    ),
    (
        EvidenceCategory.COURSEWORK,
        re.compile(r"^(?:#+\s*)?(?:relevant\s+coursework|coursework|courses|education(?:\s+and\s+coursework)?)\b[:\s]*$", re.IGNORECASE),
    ),
    (
        EvidenceCategory.TECHNICAL_SKILL,
        re.compile(r"^(?:#+\s*)?(?:technical\s+skills?|skills(?:\s+and\s+tools)?|technologies|core\s+competencies)\b[:\s]*$", re.IGNORECASE),
    ),
]


def extract_text_from_file(file_path: Union[str, Path]) -> str:
    """Read text from a PDF, Markdown, or plain-text file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_text_from_pdf(path)

    # Plain text / Markdown
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1", errors="replace")

    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"Resume file is empty: {path}")
    return cleaned


def _extract_text_from_pdf(path: Path) -> str:
    """Extract plain text from PDF using pypdf with fallback."""
    if not PYPDF_AVAILABLE:
        raise RuntimeError("pypdf package is required to parse PDF files. Install via pip install pypdf.")

    try:
        reader = pypdf.PdfReader(str(path))
        text_parts: list[str] = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        full_text = "\n\n".join(text_parts).strip()
        if not full_text:
            raise ValueError(f"Could not extract text from PDF (file may be scanned or empty): {path}")
        return full_text
    except Exception as exc:
        if isinstance(exc, (ValueError, RuntimeError)):
            raise
        raise ValueError(f"Failed to read PDF file '{path}': {exc}") from exc


def extract_skills_from_text(text: str) -> list[str]:
    """Find known technical skills, programming languages, and concepts in text."""
    found: list[str] = []
    text_lower = f" {text.lower()} "
    for skill in COMMON_TECH_SKILLS:
        pattern = r"(?<![a-zA-Z0-9_\#\+])" + re.escape(skill.lower()) + r"(?![a-zA-Z0-9_\#\+])"
        if re.search(pattern, text_lower):
            found.append(skill)
    return found


def parse_resume_evidence(
    text: str,
    source_reference: str = "Résumé",
) -> list[ResumeEvidence]:
    """Parse unstructured resume text into discrete, verifiable ResumeEvidence items."""
    lines = [line.rstrip() for line in text.splitlines()]
    if not any(line.strip() for line in lines):
        return []

    sections: list[tuple[EvidenceCategory, str, list[str]]] = []
    current_cat: EvidenceCategory | None = None
    current_title: str = "General Background"
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_lines:
                current_lines.append("")
            continue

        # Check if line matches a section header
        matched_cat = None
        for cat, pat in SECTION_PATTERNS:
            if pat.match(stripped):
                matched_cat = cat
                break

        if matched_cat:
            if current_cat is not None and current_lines:
                sections.append((current_cat, current_title, current_lines))
                current_lines = []
            elif current_lines:
                # Discard pure contact header info before first section
                current_lines = []
            current_cat = matched_cat
            current_title = stripped.lstrip("#").strip()
        else:
            current_lines.append(line)

    if current_cat is not None and current_lines:
        sections.append((current_cat, current_title, current_lines))

    # Parse entries within sections
    all_evidence: list[ResumeEvidence] = []
    for cat, section_name, sec_lines in sections:
        sec_text = "\n".join(sec_lines).strip()
        if not sec_text:
            continue

        if cat == EvidenceCategory.TECHNICAL_SKILL:
            evid = _parse_skills_section(sec_text, section_name, source_reference)
            if evid:
                all_evidence.append(evid)
        elif cat == EvidenceCategory.COURSEWORK:
            items = _parse_coursework_section(sec_text, section_name, source_reference)
            all_evidence.extend(items)
        else:
            items = _parse_project_or_experience_section(cat, sec_text, section_name, source_reference)
            all_evidence.extend(items)

    # Fallback if no specific section structure detected
    if not all_evidence and text.strip():
        skills = extract_skills_from_text(text)
        all_evidence.append(
            ResumeEvidence(
                category=EvidenceCategory.PROJECT,
                title="Extracted Experience & Background",
                description=text[:300].strip(),
                skills=skills,
                key_achievements=[],
                source_reference=source_reference,
                verification_status=VerificationStatus.UNVERIFIED,
                raw_snippet=text[:400].strip(),
            )
        )

    return all_evidence


def _parse_skills_section(
    section_text: str,
    section_name: str,
    source_ref: str,
) -> ResumeEvidence | None:
    """Consolidate technical skills section into a structured technical skill evidence item."""
    skills = extract_skills_from_text(section_text)
    # Also extract comma-separated items
    for line in section_text.splitlines():
        if ":" in line:
            _, right = line.split(":", 1)
            for part in right.split(","):
                cand = part.strip()
                if 2 <= len(cand) <= 30 and cand not in skills:
                    skills.append(cand)

    clean_skills = list(dict.fromkeys(skills))
    if not clean_skills and len(section_text.strip()) < 10:
        return None

    return ResumeEvidence(
        category=EvidenceCategory.TECHNICAL_SKILL,
        title=section_name or "Technical Skills & Competencies",
        description=f"Demonstrated technical skills and tool proficiencies: {', '.join(clean_skills[:12])}",
        skills=clean_skills[:20],
        key_achievements=[],
        source_reference=f"{source_ref} ({section_name})",
        verification_status=VerificationStatus.UNVERIFIED,
        raw_snippet=section_text[:500].strip(),
    )


def _parse_coursework_section(
    section_text: str,
    section_name: str,
    source_ref: str,
) -> list[ResumeEvidence]:
    """Parse academic coursework into structured evidence items."""
    # Split by comma or bullet
    courses: list[str] = []
    for line in section_text.splitlines():
        clean = line.strip().lstrip("•-*").strip()
        if not clean:
            continue
        if ":" in clean:
            clean = clean.split(":", 1)[1].strip()
        parts = re.split(r"[,;|•]", clean)
        for p in parts:
            p_strip = p.strip()
            if 3 <= len(p_strip) <= 60 and not p_strip.lower().startswith("relevant coursework"):
                courses.append(p_strip)

    courses = list(dict.fromkeys(courses))
    if not courses:
        return [
            ResumeEvidence(
                category=EvidenceCategory.COURSEWORK,
                title="Academic Coursework",
                description=section_text[:200].strip(),
                skills=extract_skills_from_text(section_text),
                key_achievements=[],
                source_reference=f"{source_ref} ({section_name})",
                verification_status=VerificationStatus.UNVERIFIED,
                raw_snippet=section_text[:300].strip(),
            )
        ]

    return [
        ResumeEvidence(
            category=EvidenceCategory.COURSEWORK,
            title="Relevant Academic Coursework",
            description=f"Coursework in: {', '.join(courses[:8])}",
            skills=extract_skills_from_text(section_text),
            key_achievements=[f"Completed coursework: {c}" for c in courses[:6]],
            source_reference=f"{source_ref} ({section_name})",
            verification_status=VerificationStatus.UNVERIFIED,
            raw_snippet=section_text[:400].strip(),
        )
    ]


def _parse_project_or_experience_section(
    category: EvidenceCategory,
    section_text: str,
    section_name: str,
    source_ref: str,
) -> list[ResumeEvidence]:
    """Split projects or work experience into discrete evidence records."""
    # Split by markdown headers or double newlines or clear entry delimiters
    chunks: list[str] = []
    current_chunk: list[str] = []

    for line in section_text.splitlines():
        stripped = line.strip()
        is_heading = stripped.startswith("#") or (
            stripped and not stripped.startswith(("-", "•", "*")) and len(stripped) <= 80 and not stripped.endswith((".", ","))
        )
        if is_heading and current_chunk:
            chunks.append("\n".join(current_chunk).strip())
            current_chunk = [line]
        else:
            current_chunk.append(line)

    if current_chunk:
        chunks.append("\n".join(current_chunk).strip())

    items: list[ResumeEvidence] = []
    for chunk in chunks:
        chunk_lines = [c.strip() for c in chunk.splitlines() if c.strip()]
        if not chunk_lines:
            continue

        # Extract title from first line
        first_line = chunk_lines[0].lstrip("#*-•| ").strip()
        title = first_line.split("|")[0].split("—")[0].split(" – ")[0].split(" - ")[0].strip()
        if not title:
            title = f"{section_name} Item"

        # Body description
        desc_lines = chunk_lines[1:] if len(chunk_lines) > 1 else chunk_lines
        description = " ".join([l.lstrip("-*• ") for l in desc_lines]).strip()
        if not description:
            description = title

        # Extract skills and achievements
        skills = extract_skills_from_text(chunk)
        achievements = [
            l.lstrip("-*• ") for l in desc_lines
            if any(term in l.lower() for term in ("built", "implemented", "developed", "designed", "achieved", "improved", "reduced", "%", "accuracy", "latency"))
        ]

        items.append(
            ResumeEvidence(
                category=category,
                title=title[:100],
                description=description[:500],
                skills=skills,
                key_achievements=achievements[:5],
                source_reference=f"{source_ref} ({section_name}: {title[:30]})",
                verification_status=VerificationStatus.UNVERIFIED,
                raw_snippet=chunk[:600].strip(),
            )
        )

    return items


class ResumeParser:
    """High-level resume parsing manager supporting file ingestion and evidence conversion."""

    def __init__(self) -> None:
        pass

    def parse_file(self, file_path: Union[str, Path]) -> list[ResumeEvidence]:
        """Ingest resume file (.pdf, .txt, .md) and extract structured evidence records."""
        path = Path(file_path)
        text = extract_text_from_file(path)
        return parse_resume_evidence(text, source_reference=path.name)
