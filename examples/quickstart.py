"""A.R.T.E.M.I.S. Quickstart Example.

Demonstrates the core foundation:
1. Initializing a local SQLite repository.
2. Storing a discovered professor with verified source provenance.
3. Storing an academic paper and linking it to the professor.
4. Recording verified student résumé evidence.
5. Creating a research brief connecting the student to the professor's research.
6. Generating an outreach email draft marked pending for student review.
"""

from __future__ import annotations

from artemis.db.repository import ArtemisRepository
from artemis.models.brief import ResearchBrief
from artemis.models.common import SourceProvenance, VerificationStatus
from artemis.models.email import EmailDraft, EmailDraftStatus
from artemis.models.paper import Paper
from artemis.models.professor import Professor
from artemis.models.resume import EvidenceCategory, ResumeEvidence


def main() -> None:
    print("=" * 70)
    print("A.R.T.E.M.I.S. - Minimal Foundation Demo")
    print("=" * 70)

    # 1. Initialize local SQLite repository (in-memory for this demo)
    with ArtemisRepository(":memory:") as repo:
        # 2. Add Professor with provenance
        prof_source = SourceProvenance(
            source_url="https://cs.stanford.edu/people/johndoe",
            source_name="stanford_cs_faculty_directory",
            snippet="John Doe, Professor of Computer Science. Research: Distributed Consensus & Fault Tolerance.",
            verification_status=VerificationStatus.VERIFIED,
        )

        professor = Professor(
            name="Dr. John Doe",
            title="Professor of Computer Science",
            department="Computer Science",
            institution="Stanford University",
            email="johndoe@cs.stanford.edu",
            email_status=VerificationStatus.VERIFIED,
            profile_url="https://cs.stanford.edu/people/johndoe",
            lab_url="https://systems.stanford.edu",
            scholar_url="https://scholar.google.com/citations?user=sample123",
            research_interests=["Distributed Systems", "Consensus Algorithms", "Cloud Storage"],
            sources=[prof_source],
        )
        repo.create_professor(professor)
        print(f"\n[+] Created Professor: {professor.name} ({professor.institution})")
        print(f"    - ID: {professor.id}")
        print(f"    - Verified Email: {professor.email}")
        print(f"    - Source: {professor.sources[0].source_url}")

        # 3. Add Research Paper and link to Professor
        paper_source = SourceProvenance(
            source_url="https://doi.org/10.1145/345678.901234",
            source_name="crossref",
            snippet="High-Throughput State Machine Replication in Geo-Distributed Environments",
            verification_status=VerificationStatus.VERIFIED,
        )

        paper = Paper(
            title="High-Throughput State Machine Replication in Geo-Distributed Environments",
            abstract=(
                "We propose a consensus architecture that minimizes cross-datacenter roundtrips "
                "through speculative execution and quorum partitioning."
            ),
            published_date="2024-02-10",
            year=2024,
            venue="OSDI '24",
            doi="10.1145/345678.901234",
            arxiv_id="2402.12345",
            citation_count=18,
            author_names=["John Doe", "Jane Smith"],
            sources=[paper_source],
        )
        repo.create_paper(paper)
        repo.link_professor_paper(professor.id, paper.id, relationship_type="primary_author")
        print(f"\n[+] Created & Linked Paper: '{paper.title}'")
        print(f"    - ID: {paper.id} | Venue: {paper.venue} ({paper.year}) | DOI: {paper.doi}")

        # 4. Add Student Résumé Evidence
        evidence = ResumeEvidence(
            category=EvidenceCategory.PROJECT,
            title="Raft Distributed Key-Value Store",
            description=(
                "Implemented Raft consensus in Go from scratch with log compaction, "
                "leader election, and linearizable read index leases."
            ),
            skills=["Go", "Distributed Systems", "Raft", "gRPC"],
            key_achievements=[
                "Sustained 45,000 requests/sec under 3-node cluster simulated network partitions.",
                "Verified correctness with Jepsen-style fault injection tests.",
            ],
            source_reference="Résumé Section: Systems Projects / github.com/student/raft-kv",
        )
        repo.create_evidence(evidence)
        print(f"\n[+] Stored Verified Resume Evidence: '{evidence.title}'")
        print(f"    - Category: {evidence.category.value}")
        print(f"    - Skills: {', '.join(evidence.skills)}")

        # 5. Formulate Research Brief
        brief = ResearchBrief(
            professor_id=professor.id,
            paper_id=paper.id,
            headline="Quorum Partitioning & Raft Lease Extensions",
            summary=(
                "Dr. Doe's OSDI '24 paper demonstrates speculative execution to avoid cross-WAN latency "
                "in geo-distributed consensus quorums."
            ),
            core_contributions=[
                "Partitioned quorum groups reducing inter-region coordination by 65%.",
                "Speculative commit protocol with client-side rollback handling.",
            ],
            methodology="Evaluated on 5 AWS regions across 15 physical nodes.",
            potential_alignment=(
                "Student's implementation of linearizable leases in Raft provides direct, practical "
                "familiarity with latency-sensitive quorum commitments."
            ),
            matched_evidence_ids=[evidence.id],
            open_questions=[
                "How does speculative commit recovery behave under asymmetric network partitions?",
            ],
            confidence_score=0.94,
            confidence_notes="Direct match between student's consensus project and OSDI '24 paper topic.",
            sources=[paper_source],
        )
        repo.create_brief(brief)
        print(f"\n[+] Generated Research Brief: '{brief.headline}'")
        print(f"    - Confidence: {brief.confidence_score * 100:.0f}%")
        print(f"    - Alignment: {brief.potential_alignment}")

        # 6. Prepare Email Draft (Never sent automatically, pending user review)
        draft = EmailDraft(
            professor_id=professor.id,
            brief_id=brief.id,
            recipient_email=professor.email,
            recipient_name=professor.name,
            subject="Prospective student researcher inquiry: Geo-distributed consensus protocols",
            body=(
                f"Dear {professor.name},\n\n"
                f"I recently studied your OSDI '24 paper, '{paper.title}', and was especially interested "
                "in your speculative execution approach to reduce cross-datacenter roundtrips.\n\n"
                f"In my own work ({evidence.title}), I implemented Raft consensus with leader leases to "
                "mitigate WAN roundtrips during read quorums. I would love to explore how speculative rollback "
                "mechanisms perform under asymmetric partitions.\n\n"
                "I am interested in potential research opportunities in your laboratory and would be grateful "
                "for a brief conversation if your schedule permits.\n\n"
                "Respectfully,\n"
                "[Student Name]"
            ),
            rationale="Anchored specifically on OSDI '24 paper and verified Raft implementation experience.",
            status=EmailDraftStatus.DRAFT_PENDING,
            verification_notes="Recipient email verified against Stanford faculty directory. Draft held locally.",
        )
        repo.create_draft(draft)
        print(f"\n[+] Generated Email Draft:")
        print(f"    - ID: {draft.id}")
        print(f"    - Status: {draft.status.value} (Local draft only, never sent automatically)")
        print(f"    - Recipient: {draft.recipient_name} <{draft.recipient_email}>")
        print(f"    - Subject: {draft.subject}")
        print(f"\n--- Email Body Preview ---")
        print(draft.body)
        print("--------------------------")

        # 7. Verification of retrieval
        retrieved_prof = repo.get_professor(professor.id)
        assert retrieved_prof is not None
        prof_papers = repo.get_papers_by_professor(professor.id)
        prof_briefs = repo.list_briefs_by_professor(professor.id)
        pending_drafts = repo.list_drafts(status=EmailDraftStatus.DRAFT_PENDING)

        print(f"\n[OK] Verification successful:")
        print(f"    - Retrieved Professor: {retrieved_prof.name}")
        print(f"    - Associated Papers: {len(prof_papers)}")
        print(f"    - Associated Briefs: {len(prof_briefs)}")
        print(f"    - Pending Drafts in Queue: {len(pending_drafts)}")
        print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
