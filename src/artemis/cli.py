"""Command-line interface for A.R.T.E.M.I.S. academic scouting."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from artemis.crawler.exceptions import JavaScriptRenderedPageError, RateLimitExceededError, UnsupportedPageError
from artemis.service import ArtemisScoutingService, FacultyScoutResult


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="artemis",
        description="A.R.T.E.M.I.S. — Autonomous Research Tracking, Exploration, Matching & Intelligent Scouting",
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    scout_parser = subparsers.add_parser("scout", help="Scout faculty directory and find relevant research papers")
    scout_parser.add_argument(
        "url",
        nargs="?",
        help="URL of the university faculty directory",
    )
    scout_parser.add_argument(
        "-u", "--url",
        dest="url_opt",
        help="URL of the university faculty directory (alternative flag)",
    )
    scout_parser.add_argument(
        "-k", "--keywords",
        nargs="+",
        default=[],
        help="Research-interest keywords (e.g. 'distributed systems' 'consensus' 'fault tolerance')",
    )
    scout_parser.add_argument(
        "-f", "--max-faculty",
        type=int,
        default=5,
        help="Maximum number of faculty members to scout (default: 5)",
    )
    scout_parser.add_argument(
        "-p", "--max-papers",
        type=int,
        default=3,
        help="Maximum number of publications per professor (default: 3)",
    )
    scout_parser.add_argument(
        "--db",
        default="artemis.db",
        help="Path to SQLite database file for persistence (default: artemis.db)",
    )
    scout_parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not save discovered professors and papers to database",
    )

    parsed = parser.parse_args(args)
    # Reconcile positional vs optional url
    if hasattr(parsed, "url_opt") and parsed.url_opt:
        parsed.url = parsed.url_opt
    return parsed


def sanitize_str(text: str) -> str:
    """Sanitize string for clean display on all terminal encodings (e.g. Windows cp1252)."""
    return (
        text.replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def format_table(results: list[FacultyScoutResult]) -> str:
    """Format scouting results into a clean, human-readable terminal report."""
    if not results:
        return "No faculty members or papers matching the specified criteria were discovered."

    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("A.R.T.E.M.I.S. ACADEMIC SCOUTING REPORT")
    lines.append("=" * 80)

    for i, res in enumerate(results, 1):
        prof = res.professor
        lines.append(f"\n[{i}] {prof.name}")
        lines.append("-" * 80)
        lines.append(f"  Title / Role:       {prof.title or 'Faculty'}")
        lines.append(f"  Institution:        {prof.institution}")
        if prof.department:
            lines.append(f"  Department:         {prof.department}")
        if prof.email:
            lines.append(f"  Email:              {prof.email} [{prof.email_status.value}]")
        else:
            lines.append("  Email:              [Not publicly listed on directory / unverified]")

        # Links
        links_info: list[str] = []
        if prof.profile_url:
            links_info.append(f"Profile: {prof.profile_url}")
        if prof.lab_url:
            links_info.append(f"Lab: {prof.lab_url}")
        if prof.scholar_url:
            links_info.append(f"Scholar: {prof.scholar_url}")
        if links_info:
            lines.append(f"  Links:              {' | '.join(links_info)}")

        # Research Interests
        if prof.research_interests:
            interests_str = ", ".join(prof.research_interests[:6])
            lines.append(f"  Stated Interests:   {interests_str}")

        # Top Papers
        lines.append("\n  Top Matching Papers:")
        if not res.papers:
            lines.append("    (No matching public papers retrieved from OpenAlex/arXiv)")
        else:
            for j, sp in enumerate(res.papers, 1):
                p = sp.paper
                year_str = f" ({p.year})" if p.year else ""
                venue_str = f" [{p.venue}]" if p.venue else ""
                cit_str = f" | Citations: {p.citation_count}" if p.citation_count is not None else ""
                lines.append(f"    {j}. \"{p.title}\"{year_str}{venue_str}{cit_str}")

                # Identifier & Link
                ident_str = ""
                if p.doi:
                    ident_str += f"DOI: https://doi.org/{p.doi} "
                if p.arxiv_id:
                    ident_str += f"arXiv: https://arxiv.org/abs/{p.arxiv_id} "
                if p.url and not p.doi and not p.arxiv_id:
                    ident_str += f"URL: {p.url}"
                if ident_str:
                    lines.append(f"       Identifier:     {ident_str.strip()}")

                # Match & Verification Evidence
                match_tag = "VERIFIED AFFILIATION" if sp.author_match.is_institution_matched else "UNCERTAIN (Name-Only Match)"
                lines.append(
                    f"       Scores:         Composite Relevance: {sp.composite_relevance:.2f} "
                    f"(Topic: {sp.relevance_score:.2f}, Recency: {sp.recency_score:.2f}) | "
                    f"Author Confidence: {sp.author_match.confidence:.2f} [{match_tag}]"
                )
                if sp.author_match.notes:
                    lines.append(f"       Author Match:   {sp.author_match.notes}")

                # Source Provenance
                src_urls = [s.source_url for s in p.sources]
                if src_urls:
                    lines.append(f"       Sources:        {', '.join(src_urls[:2])}")
                lines.append("")

    lines.append("=" * 80)
    return sanitize_str("\n".join(lines))


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entrypoint."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = parse_args(argv)

    if not args.command or args.command != "scout":
        print("Usage: artemis scout <URL> -k <KEYWORDS> [-f MAX_FACULTY] [-p MAX_PAPERS]")
        print("Run 'artemis scout --help' for options.")
        return 1

    if not args.url:
        print("Error: Faculty directory URL is required. Example: artemis scout https://example.edu/faculty -k distributed")
        return 1

    print(f"\n[+] A.R.T.E.M.I.S. Scouting: {args.url}")
    if args.keywords:
        print(f"    Keywords:      {', '.join(args.keywords)}")
    print(f"    Max Faculty:   {args.max_faculty} | Max Papers/Faculty: {args.max_papers}")
    print(f"    Persistence:   {'Enabled (' + args.db + ')' if not args.no_persist else 'Disabled'}")
    print("    Fetching polite directory listing...")

    try:
        with ArtemisScoutingService(db_path=args.db) as service:
            results = service.scout(
                directory_url=args.url,
                keywords=args.keywords,
                max_faculty=args.max_faculty,
                max_papers_per_faculty=args.max_papers,
                persist=not args.no_persist,
            )

        print("\n" + format_table(results))
        total_papers = sum(len(r.papers) for r in results)
        print(f"\n[OK] Scouting complete. {len(results)} faculty and {total_papers} papers processed.")
        if not args.no_persist:
            print(f"[OK] Persisted results to SQLite repository: '{args.db}'")
        return 0

    except JavaScriptRenderedPageError as exc:
        print("\n" + "!" * 80)
        print("[ERROR] JavaScript-Rendered Directory Detected:")
        print(f"  {exc}")
        print("!" * 80)
        return 2

    except RateLimitExceededError as exc:
        print(f"\n[ERROR] Rate limit exceeded: {exc}")
        return 3

    except UnsupportedPageError as exc:
        print(f"\n[ERROR] Unsupported page: {exc}")
        return 4

    except Exception as exc:
        print(f"\n[ERROR] Scouting failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
