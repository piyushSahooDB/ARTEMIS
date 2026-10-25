"""Unit tests for the polite crawler and faculty directory parser."""

from __future__ import annotations

import httpx
import pytest

from artemis.crawler.client import PoliteHttpClient
from artemis.crawler.exceptions import (
    HttpError,
    JavaScriptRenderedPageError,
    RateLimitExceededError,
)
from artemis.crawler.faculty_parser import FacultyDirectoryParser, clean_name
from artemis.models.common import VerificationStatus


class TestPoliteHttpClient:
    def test_custom_user_agent_sent(self) -> None:
        captured_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, text="<html>OK</html>")

        client = PoliteHttpClient(
            user_agent="ARTEMIS-Test/1.0",
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        res = client.get("https://example.edu/faculty")
        assert res.status_code == 200
        assert captured_headers.get("user-agent") == "ARTEMIS-Test/1.0"
        client.close()

    def test_http_error_raised_on_404(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="Not Found")

        client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        with pytest.raises(HttpError) as exc_info:
            client.get("https://example.edu/missing")
        assert exc_info.value.status_code == 404
        client.close()

    def test_rate_limit_exceeded_error_on_429(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "60"}, text="Too Many Requests")

        client = PoliteHttpClient(
            min_host_interval=0.0,
            max_retries=1,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        with pytest.raises(RateLimitExceededError):
            client.get("https://example.edu/rate-limited")
        client.close()

    def test_polite_rate_limiting_tracks_elapsed_time(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sleep_calls: list[float] = []
        monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="OK")

        client = PoliteHttpClient(
            min_host_interval=0.5,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        client.get("https://example.edu/page1")
        client.get("https://example.edu/page2")
        client.close()
        # Second request to same host within 0.5s triggers a sleep call
        assert len(sleep_calls) >= 1
        assert sleep_calls[0] > 0.0


class TestFacultyDirectoryParser:
    def test_clean_name_helper(self) -> None:
        assert clean_name("Prof. John Doe, Ph.D.") == "John Doe"
        assert clean_name("Dr. Jane Smith, M.D.") == "Jane Smith"
        assert clean_name("Professor Alan Turing") == "Alan Turing"
        assert clean_name("Assoc. Prof. Barbara Liskov") == "Barbara Liskov"

    def test_parse_card_layout_directory(self) -> None:
        html = """
        <html>
        <head><title>Faculty Directory | Department of Computer Science | Stanford University</title></head>
        <body>
            <div class="faculty-card">
                <h3><a href="/people/johndoe">Dr. John Doe</a></h3>
                <p class="title">Associate Professor of Computer Science</p>
                <p class="email"><a href="mailto:johndoe@stanford.edu">johndoe@stanford.edu</a></p>
                <p class="research">Research: Distributed Systems, Fault Tolerance, Consensus</p>
            </div>
            <div class="faculty-card">
                <h3><a href="/people/janesmith">Prof. Jane Smith</a></h3>
                <p class="title">Assistant Professor</p>
                <p class="email"><a href="mailto:jsmith@stanford.edu">jsmith@stanford.edu</a></p>
                <p class="research">Research: Machine Learning, Optimization</p>
            </div>
        </body>
        </html>
        """

        profile_html = """
        <html>
        <head><title>John Doe Profile</title></head>
        <body>
            <h1>John Doe</h1>
            <a href="https://scholar.google.com/citations?user=xyz123">Google Scholar</a>
            <a href="https://systems.stanford.edu">Lab Website</a>
            <h2>Research Interests</h2>
            <ul>
                <li>Distributed Consensus Protocols</li>
                <li>Raft and Paxos Formulations</li>
            </ul>
        </body>
        </html>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "johndoe" in url_str:
                return httpx.Response(200, text=profile_html)
            return httpx.Response(200, text=html)

        http_client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        parser = FacultyDirectoryParser(client=http_client)

        professors = parser.parse_directory(
            "https://cs.stanford.edu/faculty",
            research_keywords=["distributed", "consensus"],
            max_faculty=5,
        )

        assert len(professors) == 2
        top_prof = professors[0]
        assert top_prof.name == "John Doe"
        assert "Stanford" in top_prof.institution
        assert top_prof.title == "Associate Professor of Computer Science"
        assert top_prof.email == "johndoe@stanford.edu"
        assert top_prof.email_status == VerificationStatus.VERIFIED
        assert top_prof.scholar_url == "https://scholar.google.com/citations?user=xyz123"
        assert top_prof.lab_url == "https://systems.stanford.edu"
        assert "Distributed Consensus Protocols" in top_prof.research_interests

        # Check provenance
        assert len(top_prof.sources) >= 2
        assert any("faculty_directory" == s.source_name for s in top_prof.sources)
        assert any("faculty_profile" == s.source_name for s in top_prof.sources)
        http_client.close()

    def test_javascript_rendered_page_raises_error(self) -> None:
        spa_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Faculty Portal SPA</title></head>
        <body>
            <noscript>You need to enable JavaScript to run this app.</noscript>
            <div id="root"></div>
            <script src="/static/js/bundle.js"></script>
            <script src="/static/js/main.chunk.js"></script>
        </body>
        </html>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=spa_html)

        http_client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        parser = FacultyDirectoryParser(client=http_client)

        with pytest.raises(JavaScriptRenderedPageError) as exc_info:
            parser.parse_directory("https://spa.university.edu/directory")

        assert "client-side JavaScript (SPA)" in str(exc_info.value)
        assert "https://spa.university.edu/directory" in str(exc_info.value)
        http_client.close()

    def test_table_layout_directory_extraction(self) -> None:
        table_html = """
        <html>
        <head><title>Oxford Computer Science Faculty</title></head>
        <body>
            <table>
                <tr><th>Name</th><th>Position</th><th>Contact</th><th>Area</th></tr>
                <tr>
                    <td><a href="/faculty/turing">Dr. Alan Turing</a></td>
                    <td>Reader in Mathematics</td>
                    <td><a href="mailto:turing@ox.ac.uk">Email</a></td>
                    <td>Computability, Cryptanalysis</td>
                </tr>
                <tr>
                    <td><a href="/faculty/lovelace">Dr. Ada Lovelace</a></td>
                    <td>Lecturer</td>
                    <td><a href="mailto:lovelace@ox.ac.uk">Email</a></td>
                    <td>Symbolic Computation, Algorithms</td>
                </tr>
            </table>
        </body>
        </html>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=table_html)

        http_client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        parser = FacultyDirectoryParser(client=http_client)

        profs = parser.parse_directory(
            "https://www.cs.ox.ac.uk/people/faculty",
            max_faculty=5,
            max_profile_depth=0,  # Do not follow subpages in this test
        )

        assert len(profs) == 2
        names = [p.name for p in profs]
        assert "Alan Turing" in names
        assert "Ada Lovelace" in names
        assert profs[0].email_status == VerificationStatus.VERIFIED
        http_client.close()

    def test_anti_hallucination_leaves_missing_email_none(self) -> None:
        html = """
        <html>
        <head><title>Directory</title></head>
        <body>
            <div class="person">
                <h3><a href="/p/alice">Dr. Alice Walker</a></h3>
                <p>Assistant Professor</p>
                <p>Areas: Quantum Algorithms</p>
            </div>
            <div class="person">
                <h3><a href="/p/bob">Dr. Bob Martin</a></h3>
                <p>Professor</p>
                <p>Areas: Database Systems</p>
            </div>
        </body>
        </html>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=html)

        http_client = PoliteHttpClient(
            min_host_interval=0.0,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        parser = FacultyDirectoryParser(client=http_client)

        profs = parser.parse_directory("https://example.edu/directory", max_profile_depth=0)
        assert len(profs) == 2
        # Anti-hallucination check: missing emails must be None, never guessed
        assert profs[0].email is None
        assert profs[0].email_status == VerificationStatus.UNVERIFIED
        assert profs[1].email is None
        http_client.close()
