"""Quality control and anti-hallucination verification for outreach email drafts."""

import re
from dataclasses import dataclass, field
from typing import List, Optional

FORBIDDEN_PHRASES = [
    "as we discussed",
    "per our conversation",
    "as per your job posting",
    "saw your job posting",
    "saw your posting",
    "saw your advertisement",
    "in your lecture",
    "in your class",
    "as you know",
    "as promised",
    "according to your recent advert",
]

PLACEHOLDER_DOMAINS = [
    "example.com",
    "example.edu",
    "example.org",
    "test.com",
    "localhost",
]


@dataclass
class QualityReport:
    """Report detailing email draft quality, length, and anti-hallucination checks."""

    word_count: int
    is_word_count_ok: bool
    word_count_feedback: str
    hallucination_warnings: List[str] = field(default_factory=list)
    recipient_warnings: List[str] = field(default_factory=list)
    grounding_warnings: List[str] = field(default_factory=list)
    has_critical_issues: bool = False
    passed: bool = True


def analyze_email_draft(
    body: str,
    subject: str = "",
    recipient_email: Optional[str] = None,
    paper_title: Optional[str] = None,
    email_verification_status: Optional[str] = None,
) -> QualityReport:
    """Perform deterministic quality control and safety checks on a cold-email draft.

    Args:
        body: Plaintext body of the email.
        subject: Subject line of the email.
        recipient_email: Destination email address.
        paper_title: Title of the academic paper being referenced.
        email_verification_status: Verification level from professor record (e.g. 'verified', 'unverified').

    Returns:
        QualityReport with granular issues and pass/warn status.
    """
    words = [w for w in re.split(r"\s+", body.strip()) if w]
    word_count = len(words)

    # 1. Word count verification
    if word_count > 300:
        word_count_ok = False
        wc_feedback = f"Too long ({word_count} words). Cold research emails should be under 300 words (optimal: 120-220 words)."
    elif word_count < 40:
        word_count_ok = False
        wc_feedback = f"Too short ({word_count} words). Provide adequate context on the paper and your project connection."
    else:
        word_count_ok = True
        wc_feedback = f"Optimal length ({word_count} words). Clean and concise (< 300 words)."

    # 2. Anti-hallucination checks (forbidden phrases)
    hallucination_warnings: List[str] = []
    combined_text = (subject + " " + body).lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in combined_text:
            hallucination_warnings.append(
                f"Suspicious claim or assumed familiarity detected: '{phrase}'."
            )

    # Check for placeholder markers like [Insert Name], [Your Project]
    unfilled_placeholders = re.findall(r"\[[A-Za-z0-9_\s\-\.\?]+\]", body)
    if unfilled_placeholders:
        hallucination_warnings.append(
            f"Unfilled template brackets detected: {', '.join(set(unfilled_placeholders))}."
        )

    # 3. Recipient email checks
    recipient_warnings: List[str] = []
    if not recipient_email or not recipient_email.strip():
        recipient_warnings.append(
            "No recipient email address found. Official contact must be obtained before sending."
        )
    else:
        email_clean = recipient_email.strip().lower()
        if any(email_clean.endswith("@" + d) or ("@" + d) in email_clean for d in PLACEHOLDER_DOMAINS):
            recipient_warnings.append(
                f"Placeholder email address detected ('{recipient_email}'). Do not attempt delivery."
            )
        elif email_verification_status != "verified":
            recipient_warnings.append(
                f"Email verification status is '{email_verification_status or 'unverified'}'. Verify deliverability on official faculty page."
            )

    # 4. Paper grounding checks
    grounding_warnings: List[str] = []
    if paper_title:
        title_keywords = [
            kw.lower()
            for kw in re.findall(r"\b[A-Za-z]{4,}\b", paper_title)
            if kw.lower() not in {"using", "with", "from", "based", "approach", "study", "towards"}
        ]
        # Check if at least some substantive keyword or exact title appears
        if title_keywords and not any(kw in combined_text for kw in title_keywords):
            grounding_warnings.append(
                f"Target paper title '{paper_title[:45]}...' does not appear to be cited or referenced in the email body."
            )

    has_critical = bool(hallucination_warnings or [w for w in recipient_warnings if "Placeholder" in w or "No recipient" in w])
    passed = word_count_ok and not hallucination_warnings

    return QualityReport(
        word_count=word_count,
        is_word_count_ok=word_count_ok,
        word_count_feedback=wc_feedback,
        hallucination_warnings=hallucination_warnings,
        recipient_warnings=recipient_warnings,
        grounding_warnings=grounding_warnings,
        has_critical_issues=has_critical,
        passed=passed,
    )
