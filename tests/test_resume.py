"""Unit tests for résumé ingestion and structured evidence extraction."""

from __future__ import annotations

import io
from pathlib import Path
import pytest
import pypdf

from artemis.models.common import VerificationStatus
from artemis.models.resume import EvidenceCategory, ResumeEvidence
from artemis.resume.extractor import (
    ResumeParser,
    extract_skills_from_text,
    extract_text_from_file,
    parse_resume_evidence,
)


@pytest.fixture
def sample_resume_text() -> str:
    return """# Alex Smith
alex.smith@college.edu | +1-555-0199

## Technical Skills
Languages: Python, Go, C++, SQL
Frameworks & Tools: PyTorch, Docker, Linux, Git, SQLite

## Relevant Coursework
Distributed Systems, Operating Systems, Computer Architecture, Advanced Algorithms

## Projects
### Paxos Consensus Engine
- Implemented multi-Paxos consensus protocol in Go with leader election and state machine replication.
- Designed crash-recovery logging using write-ahead logs.
- Reduced message overhead by 18% through batched commit pipelining.

### Medical Anomaly Detection
- Built deep convolutional neural network in PyTorch for chest radiograph classification.
- Evaluated on benchmark dataset achieving 0.89 AUROC score.

## Research Experience
### Undergraduate Distributed Computing Lab
- Investigated Byzantine fault tolerance protocols under high network jitter.
- Published empirical latency benchmarks across 50 simulated geo-distributed nodes.
"""


class TestResumeExtractor:
    def test_extract_skills_from_text(self) -> None:
        text = "I have extensive experience with Python, Docker, PyTorch, and Raft consensus."
        skills = extract_skills_from_text(text)
        assert "Python" in skills
        assert "Docker" in skills
        assert "PyTorch" in skills
        assert "Raft" in skills
        assert "Consensus" in skills

    def test_parse_resume_evidence_structured_sections(self, sample_resume_text: str) -> None:
        evidence = parse_resume_evidence(sample_resume_text, source_reference="alex_resume.md")
        assert len(evidence) >= 5

        categories = [e.category for e in evidence]
        assert EvidenceCategory.TECHNICAL_SKILL in categories
        assert EvidenceCategory.COURSEWORK in categories
        assert EvidenceCategory.PROJECT in categories
        assert EvidenceCategory.RESEARCH_EXPERIENCE in categories

        # Verification status must always be UNVERIFIED for extracted claims
        for ev in evidence:
            assert ev.verification_status == VerificationStatus.UNVERIFIED
            assert ev.raw_snippet is not None
            assert len(ev.raw_snippet) > 0

        # Spot-check Paxos project
        paxos = next(e for e in evidence if "Paxos" in e.title)
        assert "Go" in paxos.skills
        assert len(paxos.key_achievements) >= 2
        assert any("Reduced message overhead" in a for a in paxos.key_achievements)
        assert "alex_resume.md" in (paxos.source_reference or "")

    def test_parse_empty_or_whitespace_text_returns_empty_list(self) -> None:
        assert parse_resume_evidence("") == []
        assert parse_resume_evidence("   \n\n\t  ") == []

    def test_extract_text_from_file_txt_and_md(self, tmp_path: Path) -> None:
        txt_file = tmp_path / "resume.txt"
        txt_file.write_text("Education:\nComputer Science BS\nProjects:\nDistributed Cache", encoding="utf-8")
        text = extract_text_from_file(txt_file)
        assert "Distributed Cache" in text

    def test_extract_text_from_nonexistent_file_raises_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            extract_text_from_file(tmp_path / "does_not_exist.txt")

    def test_extract_text_from_empty_file_raises_value_error(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.txt"
        empty.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="Resume file is empty"):
            extract_text_from_file(empty)

    def test_extract_text_from_pdf_file(self, tmp_path: Path) -> None:
        # Create a genuine minimal PDF file using pypdf
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=612, height=792)

        pdf_path = tmp_path / "test_resume.pdf"
        with open(pdf_path, "wb") as f:
            writer.write(f)

        # A completely blank PDF page has no text, so it raises ValueError
        with pytest.raises(ValueError, match="Could not extract text from PDF"):
            extract_text_from_file(pdf_path)

    def test_resume_parser_class_end_to_end(self, tmp_path: Path, sample_resume_text: str) -> None:
        file_path = tmp_path / "student_cv.md"
        file_path.write_text(sample_resume_text, encoding="utf-8")

        parser = ResumeParser()
        items = parser.parse_file(file_path)
        assert len(items) >= 4
        assert all(isinstance(i, ResumeEvidence) for i in items)
