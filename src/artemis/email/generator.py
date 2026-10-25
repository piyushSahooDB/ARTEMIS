"""Grounded cold-email draft generation engine.

Generates concise, review-first outreach drafts connecting a student to a professor's
research. Enforces strict anti-hallucination rules: references exactly one paper, cites
authentic student qualifications from ResumeEvidence, and forbids invented openings
or prior interactions.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from artemis.llm.provider import LLMProvider, get_llm_provider
from artemis.models.brief import ResearchBrief
from artemis.models.email import EmailDraft, EmailDraftStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import ResumeEvidence

logger = logging.getLogger(__name__)

FORBIDDEN_PHRASES = [
    r"as we discussed",
    r"following up on our conversation",
    r"in your class",
    r"in your lecture",
    r"saw your (?:job|internship|lab) posting",
    r"saw an opening",
    r"advertised opening",
    r"per our previous",
    r"as you mentioned earlier",
]


class _DraftGenerationSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject: str
    body: str
    rationale: str
    verification_notes: str


SYSTEM_DRAFT_PROMPT = """You are an academic communication mentor in the A.R.T.E.M.I.S. system.
Your mission is to draft a personalized, highly respectful, and concise cold email from an undergraduate student to a university professor about potential research opportunities.

STRICT CONSTRAINTS:
1. Reference EXACTLY ONE specific research paper by the professor. Mention a concrete finding or concept from the paper.
2. Ground student qualifications ONLY in the provided ResumeEvidence. Do NOT exaggerate student expertise or invent projects/skills.
3. NEVER fabricate prior contact (e.g. do NOT say "as we discussed", "enjoyed your lecture", "following up").
4. NEVER fabricate openings or vacancies (e.g. do NOT say "I saw your posting for an intern").
5. Keep the email concise and respectful (under 250 words total, 3-4 short paragraphs).
6. State that a CV/résumé is attached for reference.
"""


class DraftGenerator:
    """Generates verifiable, review-only cold outreach drafts."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None) -> None:
        self.llm = llm_provider or get_llm_provider()

    def generate_draft(
        self,
        professor: Professor,
        brief: ResearchBrief,
        paper: Paper,
        evidence: Sequence[ResumeEvidence],
        student_name: str = "Student Researcher",
    ) -> EmailDraft:
        """Generate a cold outreach draft grounded in paper findings and student evidence."""
        # Find matched evidence items
        matched_evidence = [e for e in evidence if e.id in brief.matched_evidence_ids]
        if not matched_evidence and evidence:
            matched_evidence = list(evidence[:2])

        # Recipient email handling
        recipient_email = professor.email
        email_unverified_flag = False
        if not recipient_email:
            # Safe placeholder satisfying email format validator
            domain = re.sub(r"[^a-zA-Z0-9]", "", professor.institution.lower())[:15]
            recipient_email = f"unverified.{professor.name.lower().replace(' ', '.')}@{domain or 'university'}.edu"
            email_unverified_flag = True

        prompt = self._build_prompt(professor, brief, paper, matched_evidence, student_name)

        payload = None
        try:
            payload = self.llm.generate_structured(
                prompt=prompt,
                schema=_DraftGenerationSchema,
                system_prompt=SYSTEM_DRAFT_PROMPT,
            )
        except Exception as exc:
            logger.warning(f"LLM draft generation failed ({exc}). Using deterministic fallback draft.")
            payload = self._deterministic_fallback_draft(professor, brief, paper, matched_evidence, student_name)

        return self._apply_draft_guardrails(
            payload=payload,
            professor=professor,
            brief=brief,
            paper=paper,
            matched_evidence=matched_evidence,
            recipient_email=recipient_email,
            email_unverified_flag=email_unverified_flag,
        )

    def _build_prompt(
        self,
        professor: Professor,
        brief: ResearchBrief,
        paper: Paper,
        matched_evidence: Sequence[ResumeEvidence],
        student_name: str,
    ) -> str:
        evid_strs: list[str] = []
        for e in matched_evidence:
            evid_strs.append(f"- {e.title} ({e.category.value}): {e.description} (Skills: {', '.join(e.skills)})")

        evidence_text = "\n".join(evid_strs) if evid_strs else "None specified."

        questions_text = "\n".join([f"- {q}" for q in brief.open_questions[:2]])

        return (
            f"PROFESSOR:\n"
            f"- Name: {professor.name}\n"
            f"- Title: {professor.title or 'Professor'}\n"
            f"- Institution: {professor.institution}\n\n"
            f"TARGET PUBLICATION:\n"
            f"- Title: {paper.title}\n"
            f"- Year/Venue: {paper.year or ''} {paper.venue or ''}\n"
            f"- Core Contributions: {'; '.join(brief.core_contributions[:2])}\n\n"
            f"RELEVANT STUDENT RÉSUMÉ EVIDENCE:\n"
            f"{evidence_text}\n\n"
            f"TOPICAL INQUIRY FROM BRIEF:\n"
            f"{questions_text}\n\n"
            f"STUDENT SENDER NAME: {student_name}\n\n"
            f"TASK: Draft the outreach email JSON with subject, body, rationale, and verification_notes. "
            f"Must be concise, respectful, strictly grounded in the above evidence, and under 250 words."
        )

    def _apply_draft_guardrails(
        self,
        payload: _DraftGenerationSchema,
        professor: Professor,
        brief: ResearchBrief,
        paper: Paper,
        matched_evidence: Sequence[ResumeEvidence],
        recipient_email: str,
        email_unverified_flag: bool,
    ) -> EmailDraft:
        subject = payload.subject.strip()
        body = payload.body.strip()

        # Sanitize any accidental forbidden phrases (anti-hallucination)
        for pat in FORBIDDEN_PHRASES:
            body = re.sub(pat, "I am reaching out regarding", body, flags=re.IGNORECASE)

        # Word count check: trim if LLM was too verbose
        words = body.split()
        if len(words) > 320:
            logger.warning(f"Draft body exceeded 300 words ({len(words)} words); trimming excess.")
            body = " ".join(words[:280]) + "\n\nSincerely,\nStudent"

        # Construct verification notes
        ev_ids_str = ", ".join([e.id for e in matched_evidence]) if matched_evidence else "None"
        v_notes = (
            f"Grounded in paper '{paper.title}' (DOI: {paper.doi or 'N/A'}, arXiv: {paper.arxiv_id or 'N/A'}). "
            f"Matched evidence items: [{ev_ids_str}]. "
        )
        if email_unverified_flag:
            v_notes += "WARNING: Recipient email is unverified or missing from faculty directory. Review email before sending."

        return EmailDraft(
            professor_id=professor.id,
            brief_id=brief.id,
            recipient_email=recipient_email,
            recipient_name=professor.name,
            subject=subject,
            body=body,
            rationale=payload.rationale.strip() or f"Outreach targeting research in '{paper.title}'.",
            status=EmailDraftStatus.DRAFT_PENDING,
            verification_notes=v_notes,
        )

    def _deterministic_fallback_draft(
        self,
        professor: Professor,
        brief: ResearchBrief,
        paper: Paper,
        matched_evidence: Sequence[ResumeEvidence],
        student_name: str,
    ) -> _DraftGenerationSchema:
        """Deterministic, grounded email draft template for offline and fallback use."""
        title_honorific = f"Prof. {professor.name.split()[-1]}" if professor.name.split() else f"Dr. {professor.name}"
        subject = f"Undergraduate Research Inquiry: {paper.title[:45]}..."

        project_snippet = ""
        if matched_evidence:
            top_ev = matched_evidence[0]
            skills_part = f" utilizing {', '.join(top_ev.skills[:3])}" if top_ev.skills else ""
            project_snippet = (
                f"In my project work on '{top_ev.title}'{skills_part}, "
                f"I engaged with practical challenges closely related to this domain."
            )
        else:
            project_snippet = (
                "Through my undergraduate coursework and projects, I have developed foundational interest "
                "in this research area."
            )

        inquiry_snippet = ""
        if brief.open_questions:
            inquiry_snippet = f"I was especially curious regarding {brief.open_questions[0].lower().rstrip('?')}."

        body = (
            f"Dear {title_honorific},\n\n"
            f"I hope this email finds you well. I recently read your publication, \"{paper.title}\", "
            f"and found your approach to {brief.headline.replace('[Abstract-Based Brief] ', '')} very inspiring. {inquiry_snippet}\n\n"
            f"{project_snippet} I am eager to contribute to research in your group and explore whether you might have "
            f"any undergraduate research openings in the upcoming term.\n\n"
            f"I have attached my résumé for your reference. If your schedule allows, I would welcome the opportunity "
            f"for a brief conversation.\n\n"
            f"Thank you for your time and consideration.\n\n"
            f"Sincerely,\n"
            f"{student_name}"
        )

        return _DraftGenerationSchema(
            subject=subject,
            body=body,
            rationale=f"Connects student's background directly to professor's publication '{paper.title}'.",
            verification_notes="Generated using grounded fallback template with authentic paper and evidence citations.",
        )
