"""Research brief synthesis engine bridging discovered papers and student qualifications."""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from artemis.llm.provider import LLMError, LLMProvider, get_llm_provider
from artemis.models.brief import ResearchBrief
from artemis.models.common import SourceProvenance, VerificationStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import ResumeEvidence

logger = logging.getLogger(__name__)


class _BriefGenerationSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    headline: str
    summary: str
    core_contributions: list[str] = Field(default_factory=list)
    methodology: Optional[str] = None
    limitations: list[str] = Field(default_factory=list)
    potential_alignment: str
    matched_evidence_ids: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0)
    confidence_notes: str


SYSTEM_BRIEF_PROMPT = """You are an academic research advisor in the A.R.T.E.M.I.S. system.
Your mission is to synthesize an objective, trustworthy ResearchBrief connecting a professor's publication with a university student's authentic résumé evidence.

STRICT ANTI-HALLUCINATION RULES:
1. Ground the paper summary ONLY in the provided title, abstract, and venue. If only an abstract is available, DO NOT invent methodology details, benchmarks, dataset sizes, or participant counts. Explicitly acknowledge abstract-only limitations.
2. Ground every student claim ONLY in the provided ResumeEvidence items. Use their exact IDs. Never invent skills, coursework, or projects the student has not listed.
3. If the student has NO relevant evidence for this paper, return an uncertainty confidence score (<= 0.35), set matched_evidence_ids to [], and explicitly document the gaps.
4. Formulate 2-3 thoughtful open questions the student could ask the professor that demonstrate genuine technical comprehension.
"""


class ResearchBriefSynthesizer:
    """Synthesizes structured research briefs connecting papers to verified student qualifications."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None) -> None:
        self.llm = llm_provider or get_llm_provider()

    def synthesize(
        self,
        professor: Professor,
        paper: Paper,
        evidence: Sequence[ResumeEvidence],
        full_text: Optional[str] = None,
    ) -> ResearchBrief:
        """Synthesize a grounded ResearchBrief linking paper findings to authentic student evidence."""
        is_abstract_only = full_text is None
        valid_evidence_map = {ev.id: ev for ev in evidence}

        # Build detailed prompt
        prompt = self._build_prompt(professor, paper, evidence, is_abstract_only=is_abstract_only)

        # Attempt structured generation via LLM
        payload = None
        try:
            payload = self.llm.generate_structured(
                prompt=prompt,
                schema=_BriefGenerationSchema,
                system_prompt=SYSTEM_BRIEF_PROMPT,
            )
        except Exception as exc:
            logger.warning(f"LLM structured generation failed for brief ({exc}). Using deterministic fallback synthesis.")
            payload = self._deterministic_fallback_synthesis(professor, paper, evidence, is_abstract_only)

        # Grounding & Validation Guardrails
        validated_brief = self._apply_grounding_guardrails(
            payload=payload,
            professor=professor,
            paper=paper,
            valid_evidence_map=valid_evidence_map,
            is_abstract_only=is_abstract_only,
        )

        return validated_brief

    def _build_prompt(
        self,
        professor: Professor,
        paper: Paper,
        evidence: Sequence[ResumeEvidence],
        is_abstract_only: bool,
    ) -> str:
        evid_descriptions: list[str] = []
        for ev in evidence:
            skills_str = ", ".join(ev.skills) if ev.skills else "None specified"
            achieve_str = "; ".join(ev.key_achievements) if ev.key_achievements else "None"
            evid_descriptions.append(
                f"- [ID: {ev.id}] Category: {ev.category.value} | Title: {ev.title}\n"
                f"  Description: {ev.description}\n"
                f"  Skills: {skills_str}\n"
                f"  Key Achievements: {achieve_str}\n"
                f"  Verification State: {ev.verification_status.value} (self-reported)"
            )

        evidence_block = "\n".join(evid_descriptions) if evid_descriptions else "No student résumé evidence provided."

        text_notice = (
            "NOTICE: Full manuscript text is NOT available. Only the published title, venue, and abstract are provided. "
            "You MUST prefix your headline with '[Abstract-Based Brief]' and state that methodology and limitations are derived solely from the abstract."
            if is_abstract_only
            else "Full publication text is available."
        )

        return (
            f"PROFESSOR:\n"
            f"- Name: {professor.name}\n"
            f"- Institution: {professor.institution}\n"
            f"- Department: {professor.department or 'N/A'}\n"
            f"- Research Interests: {', '.join(professor.research_interests)}\n\n"
            f"PUBLICATION:\n"
            f"- Title: {paper.title}\n"
            f"- Year: {paper.year or 'N/A'}\n"
            f"- Venue: {paper.venue or 'N/A'}\n"
            f"- DOI: {paper.doi or 'N/A'}\n"
            f"- arXiv: {paper.arxiv_id or 'N/A'}\n"
            f"- Citations: {paper.citation_count if paper.citation_count is not None else 'N/A'}\n"
            f"- Abstract: {paper.abstract or 'No abstract available.'}\n"
            f"- Source Status: {text_notice}\n\n"
            f"STUDENT AUTHENTIC RÉSUMÉ EVIDENCE:\n"
            f"{evidence_block}\n\n"
            f"TASK:\n"
            f"Synthesize the ResearchBrief JSON object connecting this paper to the student's authentic evidence. "
            f"Strictly adhere to anti-hallucination rules."
        )

    def _apply_grounding_guardrails(
        self,
        payload: _BriefGenerationSchema,
        professor: Professor,
        paper: Paper,
        valid_evidence_map: dict[str, ResumeEvidence],
        is_abstract_only: bool,
    ) -> ResearchBrief:
        headline = payload.headline.strip()
        summary = payload.summary.strip()

        # Enforce abstract-only labeling
        if is_abstract_only:
            if not headline.startswith("[Abstract-Based Brief]"):
                headline = f"[Abstract-Based Brief] {headline}"
            methodology = (
                payload.methodology
                if payload.methodology and "abstract" in payload.methodology.lower()
                else "Derived solely from published abstract; detailed experimental setup requires full manuscript text."
            )
            limitations = payload.limitations or [
                "Analysis bounded by published abstract; full manuscript parameters and edge cases were not evaluated."
            ]
        else:
            methodology = payload.methodology or "Extracted from publication manuscript."
            limitations = payload.limitations

        # Validate matched_evidence_ids (reject fabricated IDs)
        filtered_evidence_ids: list[str] = []
        for eid in payload.matched_evidence_ids:
            if eid in valid_evidence_map:
                filtered_evidence_ids.append(eid)
            else:
                logger.warning(f"Discarded fabricated evidence ID '{eid}' from LLM response.")

        alignment = payload.potential_alignment.strip()
        confidence = payload.confidence_score
        confidence_notes = payload.confidence_notes.strip()
        gaps = payload.gaps or []

        # If no genuine evidence items matched
        if not filtered_evidence_ids:
            confidence = min(0.35, confidence)
            alignment = (
                f"Uncertain connection: No authentic student résumé evidence directly matches this paper's core requirements. "
                f"Preliminary topical connection only."
            )
            confidence_notes = "Evidence is insufficient; student background does not exhibit direct overlap with paper prerequisites."
            if not gaps:
                gaps.append("Student résumé does not demonstrate prior research, coursework, or project experience in this paper's domain.")

        # Attach source provenance
        src_url = paper.url or (f"https://doi.org/{paper.doi}" if paper.doi else f"https://arxiv.org/abs/{paper.arxiv_id}" if paper.arxiv_id else "https://openalex.org")
        provenance = SourceProvenance(
            source_url=src_url,
            source_name="publication_record",
            snippet=f"Paper: {paper.title} ({paper.year or 'n.d.'})",
            verification_status=VerificationStatus.VERIFIED if paper.doi or paper.arxiv_id else VerificationStatus.UNVERIFIED,
        )

        return ResearchBrief(
            professor_id=professor.id,
            paper_id=paper.id,
            headline=headline,
            summary=summary,
            core_contributions=payload.core_contributions or ["Core theoretical and empirical findings reported in publication."],
            methodology=methodology,
            potential_alignment=alignment,
            matched_evidence_ids=filtered_evidence_ids,
            limitations=limitations,
            gaps=gaps,
            open_questions=payload.open_questions or [
                f"What are the most promising near-term extensions of your findings in {paper.title}?",
                "How do these results generalize to broader deployment environments?",
            ],
            confidence_score=round(max(0.0, min(1.0, confidence)), 2),
            confidence_notes=confidence_notes,
            sources=[provenance],
        )

    def _deterministic_fallback_synthesis(
        self,
        professor: Professor,
        paper: Paper,
        evidence: Sequence[ResumeEvidence],
        is_abstract_only: bool,
    ) -> _BriefGenerationSchema:
        """Deterministic heuristic fallback when LLM is unavailable or outputs malformed text."""
        headline_prefix = "[Abstract-Based Brief] " if is_abstract_only else ""
        headline = f"{headline_prefix}{paper.title[:70]}"
        summary = (
            paper.abstract[:400].strip()
            if paper.abstract
            else f"Investigation into {', '.join(professor.research_interests[:2]) or 'computing systems'} by {professor.name}."
        )

        # Keyword matching across evidence
        paper_tokens = set(re.findall(r"\w+", (paper.title + " " + (paper.abstract or "")).lower()))
        matched_ids: list[str] = []
        matched_skills: list[str] = []

        for ev in evidence:
            ev_tokens = set(re.findall(r"\w+", (ev.title + " " + ev.description + " " + " ".join(ev.skills)).lower()))
            overlap = paper_tokens.intersection(ev_tokens)
            # Exclude common stopwords
            useful_overlap = {w for w in overlap if len(w) > 3 and w not in ("this", "that", "with", "from", "using", "have", "more")}
            if useful_overlap:
                matched_ids.append(ev.id)
                matched_skills.extend(ev.skills)

        matched_skills = list(dict.fromkeys(matched_skills))

        if matched_ids:
            alignment = (
                f"Student demonstrates relevant background through project/coursework in {', '.join(matched_skills[:4])}, "
                f"which directly connects to {professor.name}'s research on {paper.title[:50]}."
            )
            conf = 0.80
            notes = "Student evidence shows concrete keyword and project overlap with publication topics."
            gaps = [f"Requires deeper mastery of advanced techniques specific to {paper.title[:40]}."]
        else:
            alignment = "Uncertain connection: No direct overlap between student's extracted evidence and paper requirements."
            conf = 0.30
            notes = "Evidence is insufficient; student background does not exhibit direct overlap with paper prerequisites."
            gaps = ["Student résumé does not demonstrate prior research or coursework in this specific domain."]

        methodology_note = (
            "Derived solely from published abstract; full experimental methodology and detailed dataset parameters require access to complete manuscript."
            if is_abstract_only
            else "Extracted from publication manuscript."
        )

        return _BriefGenerationSchema(
            headline=headline,
            summary=summary,
            core_contributions=[
                f"Presents findings and techniques for {paper.title[:60]}.",
                f"Published in {paper.venue or 'academic venue'} ({paper.year or 'recent'}).",
            ],
            methodology=methodology_note,
            limitations=[
                "Analysis bounded by published abstract; full manuscript parameters and edge cases were not evaluated."
            ] if is_abstract_only else [],
            potential_alignment=alignment,
            matched_evidence_ids=matched_ids[:3],
            gaps=gaps,
            open_questions=[
                f"How does the methodology in '{paper.title[:50]}' scale under real-world workload constraints?",
                "What open questions remain from this work that an undergraduate researcher could assist in tackling?",
            ],
            confidence_score=conf,
            confidence_notes=notes,
        )
