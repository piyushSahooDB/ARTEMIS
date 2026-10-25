"""Replaceable LLM Provider interface and implementations."""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Mapping, Optional, Type, TypeVar
from pydantic import BaseModel

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base exception for LLM provider errors."""


class LLMProvider(ABC):
    """Abstract interface for replaceable LLM providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        """Generate a text response from the model."""

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
    ) -> T:
        """Generate and parse structured data validated by a Pydantic schema."""
        augmented_prompt = (
            f"{prompt}\n\n"
            f"CRITICAL REQUIREMENT: Output your response as a valid, strictly formatted JSON object "
            f"conforming to this schema: {json.dumps(schema.model_json_schema())}.\n"
            f"Do not include markdown code block backticks (like ```json). Return ONLY raw JSON."
        )
        raw_text = self.generate(augmented_prompt, system_prompt=system_prompt, temperature=0.1)
        cleaned = self._clean_json_text(raw_text)
        try:
            data = json.loads(cleaned)
            return schema.model_validate(data)
        except Exception as exc:
            raise LLMError(f"Failed to parse LLM response into schema {schema.__name__}: {exc}\nRaw text: {raw_text[:200]}") from exc

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """Strip markdown fences, leading/trailing whitespace, or commentary."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Find first { and last }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return cleaned[start : end + 1]
        return cleaned


class MockLLMProvider(LLMProvider):
    """Deterministic, offline mock LLM provider for zero-network testing and offline development."""

    def __init__(
        self,
        default_response: Optional[str] = None,
        canned_responses: Optional[Mapping[str, str]] = None,
        handler: Optional[Callable[[str, Optional[str]], str]] = None,
        raise_error: Optional[Exception] = None,
    ) -> None:
        self.default_response = default_response
        self.canned_responses = dict(canned_responses or {})
        self.handler = handler
        self.raise_error = raise_error
        self.call_history: list[dict[str, Any]] = []

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        self.call_history.append({"prompt": prompt, "system_prompt": system_prompt})
        if self.raise_error:
            raise self.raise_error

        if self.handler:
            return self.handler(prompt, system_prompt)

        for key, resp in self.canned_responses.items():
            if key.lower() in prompt.lower():
                return resp

        if self.default_response is not None:
            return self.default_response

        # Default intelligent fallback generator based on prompt inspection
        return self._generate_default_heuristic_response(prompt)

    def _generate_default_heuristic_response(self, prompt: str) -> str:
        prompt_lower = prompt.lower()

        if "_draftgenerationschema" in prompt_lower or ("draft" in prompt_lower and ("subject" in prompt_lower or "outreach" in prompt_lower)):
            name_match = re.search(r"STUDENT SENDER NAME:\s*([^\n\r]+)", prompt)
            sender_name = name_match.group(1).strip() if name_match else "Student"

            title_match = re.search(r"TARGET PUBLICATION:.*?-\s*Title:\s*([^\r\n]+)", prompt, flags=re.DOTALL) or re.search(r"Title:\s*([^\n\r]+)", prompt)
            paper_title = title_match.group(1).strip() if title_match else "Recent Publication"

            # Extract student's relevant project from evidence block
            top_ev_title = "academic projects"
            top_skills = ""
            if "RELEVANT STUDENT RÉSUMÉ EVIDENCE:" in prompt:
                ev_part = prompt[prompt.find("RELEVANT STUDENT RÉSUMÉ EVIDENCE:") : prompt.find("TOPICAL INQUIRY")]
                ev_lines = [l.strip() for l in ev_part.splitlines() if l.strip().startswith("-")]
                if ev_lines:
                    first_ev = ev_lines[0].lstrip("- ")
                    top_ev_title = first_ev.split("(")[0].split(":")[0].strip()
                    sk_match = re.search(r"\(Skills:\s*([^)]+)\)", first_ev)
                    if sk_match and sk_match.group(1).strip() != "None specified":
                        top_skills = f" utilizing {sk_match.group(1).strip()}"

            return json.dumps({
                "subject": f"Undergraduate Research Inquiry: {paper_title[:50]}",
                "body": (
                    "Dear Professor,\n\n"
                    f"I recently studied your research on '{paper_title}' and was particularly intrigued by your findings and methodology. "
                    f"In my project work on '{top_ev_title}'{top_skills}, I engaged with practical challenges closely related to this domain.\n\n"
                    "I am very interested in exploring potential undergraduate research opportunities in your lab to contribute to extensions of this work. Would you be open to a brief conversation if you have availability?\n\n"
                    "Thank you for your time and research leadership.\n\n"
                    f"Sincerely,\n{sender_name}"
                ),
                "rationale": f"Directly links student's work on '{top_ev_title}' to the professor's paper '{paper_title}', avoiding inflated claims or assumed openings.",
                "verification_notes": "Referenced paper and student evidence verified against stored records.",
            })

        if "_briefgenerationschema" in prompt_lower or "researchbrief" in prompt_lower or "core_contributions" in prompt_lower or "brief" in prompt_lower:
            # Check if abstract only
            is_abstract_only = (
                "abstract only" in prompt_lower
                or "only published abstract" in prompt_lower
                or "not available" in prompt_lower
            )
            prefix = "[Abstract-Based Brief] " if is_abstract_only else ""
            methodology_text = (
                "Derived solely from published abstract; full experimental methodology requires manuscript access."
                if is_abstract_only
                else "Evaluated via rigorous experimental methodology reported in manuscript."
            )
            title_match = re.search(r"PUBLICATION:.*?-\s*Title:\s*([^\r\n]+)", prompt, flags=re.DOTALL) or re.search(r"Title:\s*([^\n\r]+)", prompt)
            paper_title = title_match.group(1).strip() if title_match else "Consensus Protocols in Distributed Networks"

            # Extract abstract if present
            abstract_text = ""
            abs_match = re.search(r"- Abstract:\s*([^\n\r]+(?:\n[^\n\r]+)*?)(?=\n-[A-Z]|\nSTUDENT|\nTASK)", prompt)
            if abs_match:
                abstract_text = abs_match.group(1).strip()

            summary = (
                abstract_text[:350].strip()
                if abstract_text and abstract_text != "No abstract available."
                else f"Investigation and empirical evaluation of methodologies in '{paper_title}'."
            )

            # Score evidence blocks in prompt by overlap with paper
            paper_tokens = set(re.findall(r"\w+", (paper_title + " " + abstract_text).lower()))
            ev_blocks = re.findall(r"-\s*\[ID:\s*(evid_[^\]]+)\]([^\n\r]+(?:\n\s{2,}[^\n\r]+)*)", prompt)
            scored_ids: list[tuple[int, str]] = []
            for eid, block in ev_blocks:
                tokens = set(re.findall(r"\w+", block.lower()))
                overlap = {
                    t for t in paper_tokens.intersection(tokens)
                    if len(t) > 3 and t not in ("this", "that", "with", "from", "using", "have", "more", "built", "designed", "implemented")
                }
                if overlap:
                    scored_ids.append((len(overlap), eid))

            scored_ids.sort(key=lambda x: x[0], reverse=True)
            selected_ids = [eid for _, eid in scored_ids[:2]]
            if not selected_ids:
                # Fallback to any evidence IDs found in prompt
                found_ids = re.findall(r"\[ID:\s*([a-zA-Z0-9_-]+)\]", prompt) or re.findall(r"ID:\s*([a-zA-Z0-9_-]+)", prompt)
                matched_ids = [fid for fid in found_ids if fid.startswith("evid_")]
                if not matched_ids and "evid_" in prompt:
                    matched_ids = re.findall(r"(evid_[a-zA-Z0-9_]+)", prompt)
                selected_ids = list(dict.fromkeys(matched_ids))[:2]

            alignment = (
                "Student has practical experience building projects and coursework that directly connect to the paper's focus."
                if selected_ids
                else "Uncertain connection: No authentic student résumé evidence directly matches this paper's core requirements. Preliminary topical connection only."
            )
            conf = 0.85 if selected_ids else 0.30

            # Derive contributions from abstract sentences if available
            contributions = [
                f"Presents techniques and experimental results for {paper_title[:50]}.",
                "Demonstrates empirical evaluation under realistic workload scenarios.",
            ]
            if abstract_text and "." in abstract_text:
                sentences = [s.strip() for s in abstract_text.split(".") if len(s.strip()) > 30]
                if len(sentences) >= 2:
                    contributions = [f"{sentences[0]}.", f"{sentences[1]}."]

            return json.dumps({
                "headline": f"{prefix}{paper_title}",
                "summary": summary,
                "core_contributions": contributions,
                "methodology": methodology_text,
                "potential_alignment": alignment,
                "matched_evidence_ids": selected_ids,
                "open_questions": [
                    f"How does the methodology in '{paper_title[:45]}' scale under challenging real-world deployment constraints?",
                    "What are the most promising near-term extensions of this work that an undergraduate researcher could explore?",
                ],
                "confidence_score": conf,
                "confidence_notes": (
                    "Grounding verified against student project evidence and published publication findings."
                    if selected_ids
                    else "Evidence is insufficient; student background does not exhibit direct overlap with paper prerequisites."
                ),
            })

        return "This is a deterministic mock LLM response."


class GeminiLLMProvider(LLMProvider):
    """Production LLM provider using Google Gemini REST API via httpx.

    Reads API key securely from GEMINI_API_KEY environment variable. Never hardcodes keys.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
        timeout: float = 30.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", model)
        self.timeout = timeout
        self.client = client or httpx.Client(timeout=timeout)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        if not self.api_key or not self.api_key.strip():
            raise LLMError(
                "GEMINI_API_KEY is not set. Set GEMINI_API_KEY in your environment or .env file, "
                "or use ARTEMIS_LLM_PROVIDER=mock for offline deterministic execution."
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        params = {"key": self.api_key}

        contents: list[dict[str, Any]] = []
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"System Instructions:\n{system_prompt}\n\nPlease confirm."}],
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will strictly follow these instructions."}],
            })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}],
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            },
        }

        try:
            response = self.client.post(url, params=params, json=payload)
            if response.status_code != 200:
                raise LLMError(f"Gemini API error ({response.status_code}): {response.text}")

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMError("Gemini API returned no candidates.")

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise LLMError("Gemini API candidate contained no parts.")

            return parts[0].get("text", "").strip()

        except httpx.RequestError as exc:
            raise LLMError(f"Network error communicating with Gemini API: {exc}") from exc


def get_llm_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMProvider:
    """Factory creating configured LLM provider (mock or gemini)."""
    name = (provider_name or os.getenv("ARTEMIS_LLM_PROVIDER") or "mock").lower().strip()
    if name == "mock":
        return MockLLMProvider()
    elif name == "gemini":
        return GeminiLLMProvider(api_key=api_key)
    else:
        raise ValueError(f"Unsupported LLM provider: '{name}'. Supported providers: 'mock', 'gemini'.")
