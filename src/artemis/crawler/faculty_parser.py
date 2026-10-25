"""HTML parser extracting verified faculty records from university directories."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from artemis.crawler.client import PoliteHttpClient
from artemis.crawler.exceptions import JavaScriptRenderedPageError
from artemis.models.common import SourceProvenance, VerificationStatus
from artemis.models.professor import Professor

# Prefixes and suffixes to strip from faculty names
NAME_PREFIXES = ("prof.", "dr.", "professor", "assoc. prof.", "asst. prof.", "mr.", "ms.", "mrs.")
NAME_SUFFIXES = (", ph.d.", ", phd", ", m.d.", ", md", ", facm", ", fsa", ", obe", ", cbe")

TITLE_PATTERNS = [
    re.compile(r"\bassociate\s+professor(?:\s+of\s+[A-Za-z\s]+)?\b", re.IGNORECASE),
    re.compile(r"\bassistant\s+professor(?:\s+of\s+[A-Za-z\s]+)?\b", re.IGNORECASE),
    re.compile(r"\bdistinguished\s+professor(?:\s+of\s+[A-Za-z\s]+)?\b", re.IGNORECASE),
    re.compile(r"\bclinical\s+professor\b", re.IGNORECASE),
    re.compile(r"\badjunct\s+professor\b", re.IGNORECASE),
    re.compile(r"\bprofessor(?:\s+of\s+[A-Za-z\s]+)?\b", re.IGNORECASE),
    re.compile(r"\b(senior\s+)?lecturer(?:\s+in\s+[A-Za-z\s]+)?\b", re.IGNORECASE),
    re.compile(r"\bpostdoctoral\s+(?:fellow|researcher|scholar)\b", re.IGNORECASE),
    re.compile(r"\bdepartment\s+chair\b", re.IGNORECASE),
    re.compile(r"\bresearch\s+scientist\b", re.IGNORECASE),
]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def clean_name(raw_name: str) -> str:
    """Clean title prefixes, suffixes, and excess whitespace from a person's name."""
    text = raw_name.strip()
    for prefix in NAME_PREFIXES:
        if text.lower().startswith(prefix):
            text = text[len(prefix) :].strip()
    for suffix in NAME_SUFFIXES:
        if text.lower().endswith(suffix):
            text = text[: -len(suffix)].strip()
    return re.sub(r"\s+", " ", text)


def clean_title(raw_title: str | None) -> str | None:
    """Trim trailing field labels from extracted title string."""
    if not raw_title:
        return None
    cleaned = re.sub(r"\s+", " ", raw_title).strip()
    for barrier in ("research areas", "research interests", "research", "email", "phone", "office", "interests"):
        pattern = re.compile(rf"\s+{barrier}\b.*", re.IGNORECASE)
        cleaned = pattern.sub("", cleaned).strip()
    return cleaned or None


KNOWN_INSTITUTION_DOMAINS: dict[str, str] = {
    "iitd": "Indian Institute of Technology Delhi",
    "iitm": "Indian Institute of Technology Madras",
    "iitb": "Indian Institute of Technology Bombay",
    "iitk": "Indian Institute of Technology Kanpur",
    "iitkgp": "Indian Institute of Technology Kharagpur",
    "iitr": "Indian Institute of Technology Roorkee",
    "iitg": "Indian Institute of Technology Guwahati",
    "iith": "Indian Institute of Technology Hyderabad",
    "iiti": "Indian Institute of Technology Indore",
    "iitbhu": "IIT BHU Varanasi",
    "iisc": "Indian Institute of Science",
    "iiitd": "Indraprastha Institute of Information Technology Delhi",
    "iiith": "IIIT Hyderabad",
    "iiitb": "IIIT Bangalore",
    "tifr": "Tata Institute of Fundamental Research",
    "cmi": "Chennai Mathematical Institute",
    "isi": "Indian Statistical Institute",
    "bits-pilani": "BITS Pilani",
    "nitt": "National Institute of Technology Tiruchirappalli",
    "nitk": "National Institute of Technology Karnataka",
    "nitw": "National Institute of Technology Warangal",
    "stanford": "Stanford University",
    "mit": "Massachusetts Institute of Technology",
    "cmu": "Carnegie Mellon University",
    "berkeley": "UC Berkeley",
    "harvard": "Harvard University",
    "ox": "University of Oxford",
    "cam": "University of Cambridge",
}


def infer_institution(soup: BeautifulSoup, url: str) -> str:
    """Infer institution name from domain hostname, page title, or meta tags."""
    # 1. Authoritative check via domain hostname and known institution codes
    domain = urlparse(url).netloc.lower()
    domain_parts = domain.split(".")
    for part in domain_parts:
        if part in KNOWN_INSTITUTION_DOMAINS:
            return KNOWN_INSTITUTION_DOMAINS[part]

    # 2. Check title tag for clean institution names
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        title = title_tag.string.strip()
        parts = [p.strip() for p in re.split(r"[|\-–—]", title) if p.strip()]
        for part in reversed(parts):
            if any(term in part.lower() for term in ("university", "institute", "college", "school")):
                if len(part) <= 60:
                    return part

    # 3. Check header/brand for specific, strict institutional phrases
    for tag in soup.find_all(["header", "nav", "div"], class_=re.compile(r"header|brand|navbar|logo", re.I)):
        text = tag.get_text(separator=" ", strip=True)
        m = re.search(r"\b(Indian Institute of Technology\s+[A-Z][a-z]+|National Institute of Technology\s+[A-Z][a-z]+)\b", text)
        if m:
            return m.group(1).strip()

    # 4. Fallback: filter out common academic TLDs, SLDs, and subdomains
    filtered = [
        p for p in domain_parts
        if p not in (
            "www", "homecse", "cse", "cs", "dept", "department", "faculty", "staff",
            "ac", "edu", "ernet", "gov", "res", "in", "uk", "au", "com", "org", "net"
        )
    ]
    if filtered:
        return filtered[-1].capitalize() + " University"

    return "Unknown Institution"


def infer_department(soup: BeautifulSoup) -> str | None:
    """Infer academic department from headings or page meta."""
    for heading in soup.find_all(["h1", "h2"]):
        text = heading.get_text(strip=True)
        if any(term in text.lower() for term in ("department of", "school of", "division of", "faculty of")):
            return text
    return None


def detect_spa_indicators(soup: BeautifulSoup) -> bool:
    """Detect whether a page requires client-side JavaScript execution (SPA)."""
    # 1. Check for noscript warnings about JavaScript
    for noscript in soup.find_all("noscript"):
        text = noscript.get_text().lower()
        if any(phrase in text for phrase in ("enable javascript", "javascript is required", "need to enable javascript")):
            return True

    # 2. Check for empty root app containers typical in React/Vue/Angular/Next.js
    for root_id in ("root", "app", "__next", "react-app"):
        root_div = soup.find(id=root_id)
        if root_div and len(root_div.get_text(strip=True)) < 50:
            scripts = soup.find_all("script")
            if len(scripts) >= 2:
                return True

    # Check for Angular / custom component root tags (e.g. <app-root>, <app-main>)
    for app_tag in soup.find_all(lambda tag: tag.name and (tag.name.startswith("app-") or tag.name in ("app", "root"))):
        if len(app_tag.get_text(strip=True)) < 50:
            return True

    # 3. Check for pages with almost no textual content but client-side bundles
    body = soup.find("body")
    if body:
        visible_text = body.get_text(strip=True)
        if len(visible_text) < 150 and soup.find_all("script"):
            return True

    return False


class FacultyDirectoryParser:
    """Parser discovering faculty members from university directory HTML pages."""

    def __init__(self, client: PoliteHttpClient | None = None) -> None:
        self.client = client or PoliteHttpClient()

    def parse_directory(
        self,
        directory_url: str,
        research_keywords: list[str] | None = None,
        max_faculty: int = 10,
        max_profile_depth: int = 10,
        institution_name: str | None = None,
    ) -> list[Professor]:
        """Fetch and parse faculty members from directory URL, following profiles politely."""
        response = self.client.get(directory_url)
        soup = BeautifulSoup(response.text, "html.parser")

        institution = institution_name or infer_institution(soup, directory_url)
        default_dept = infer_department(soup)

        candidates = self._extract_faculty_candidates(soup, directory_url, institution, default_dept)

        if not candidates and detect_spa_indicators(soup):
            raise JavaScriptRenderedPageError(directory_url)

        # Keyword filtering & relevance scoring
        if research_keywords:
            candidates = self._filter_and_rank_by_keywords(candidates, research_keywords)

        # Bound results to requested maximum
        selected = candidates[:max_faculty]

        # Polite subpage exploration (fetching profile pages up to max_profile_depth)
        enriched_professors: list[Professor] = []
        for i, prof in enumerate(selected):
            if i < max_profile_depth and prof.profile_url:
                try:
                    prof = self._enrich_from_profile(prof)
                except Exception:
                    # Never crash the entire directory extraction if a single subpage fails
                    pass
            enriched_professors.append(prof)

        return enriched_professors

    def _extract_faculty_candidates(
        self,
        soup: BeautifulSoup,
        base_url: str,
        institution: str,
        default_dept: str | None,
    ) -> list[Professor]:
        """Extract candidate professors using multi-strategy layout heuristics."""
        professors: list[Professor] = []
        seen_names: set[str] = set()

        # Strategy 1: Look for common faculty cards / person containers
        card_selectors = [
            "div.single-team-area", "div.fac-card", "div.team-grid",
            "div.faculty-member", "div.faculty-card", "div.person", "div.directory-item",
            "div.profile-card", "div.views-row", "article.person", "article.faculty",
            "li.faculty-member", "li.person", "div.team-member", "div.team-item", "div.card",
            "div.col-md-4", "div.col-sm-6"
        ]

        found_nodes: list[Tag] = []
        for sel in card_selectors:
            matches = soup.select(sel)
            if len(matches) >= 2:
                found_nodes = matches
                break

        if found_nodes:
            for node in found_nodes:
                prof = self._parse_card_node(node, base_url, institution, default_dept)
                if prof and prof.name.lower() not in seen_names:
                    seen_names.add(prof.name.lower())
                    professors.append(prof)

        # Strategy 2: Table layout fallback
        if not professors:
            professors = self._parse_table_layout(soup, base_url, institution, default_dept)

        # Strategy 3: Heading + link layout fallback
        if not professors:
            professors = self._parse_heading_list_layout(soup, base_url, institution, default_dept)

        return professors

    def _parse_card_node(
        self,
        node: Tag,
        base_url: str,
        institution: str,
        default_dept: str | None,
    ) -> Professor | None:
        """Parse an individual card or element container."""
        # Find name and profile link
        link = node.find("a", href=True)
        name_tag = node.find(["h2", "h3", "h4", "h5", "strong", "b"])

        raw_name: str | None = node.get("data-name")
        profile_url: str | None = None
        if node.get("data-profile-link"):
            profile_url = urljoin(base_url, node.get("data-profile-link"))

        if not raw_name:
            if link and link.get_text(strip=True):
                link_text = link.get_text(strip=True)
                if not any(ign in link_text.lower() for ign in ("read more", "view profile", "website", "profile")):
                    raw_name = link_text
                    if not profile_url:
                        profile_url = urljoin(base_url, link["href"])
            elif name_tag:
                raw_name = name_tag.get_text(strip=True)

        if not raw_name:
            return None

        name = clean_name(raw_name)
        if len(name.split()) < 2 or len(name) > 60:
            return None

        # Resolve profile link if link was just 'View Profile'
        if not profile_url and link:
            profile_url = urljoin(base_url, link["href"])

        text_content = node.get_text(separator=" ", strip=True)

        # Extract title
        title: str | None = None
        if node.get("data-designation"):
            title = clean_title(node.get("data-designation"))

        if not title:
            title_tag = node.find(class_=re.compile(r"title|position|role|designation|rank", re.I))
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                for pat in TITLE_PATTERNS:
                    m = pat.search(title_text)
                    if m:
                        title = m.group(0).strip()
                        break
                if not title and len(title_text) <= 80:
                    title = title_text

        if not title:
            for pat in TITLE_PATTERNS:
                m = pat.search(text_content)
                if m:
                    title = m.group(0).strip()
                    break

        title = clean_title(title)

        # Extract email
        email: str | None = None
        raw_mail = node.get("data-mail")
        if raw_mail:
            deobf = re.sub(r"\[at\]|\(at\)", "@", raw_mail)
            deobf = re.sub(r"\[dot\]|\(dot\)", ".", deobf).strip()
            if EMAIL_REGEX.match(deobf):
                email = deobf

        if not email:
            mailto = node.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
            if mailto and mailto.get("href"):
                raw_email = mailto["href"].split(":", 1)[1].split("?")[0].strip()
                if EMAIL_REGEX.match(raw_email):
                    email = raw_email
        if not email:
            em_match = EMAIL_REGEX.search(text_content)
            if em_match:
                email = em_match.group(0)

        # Extract research interests
        interests: list[str] = []
        data_res = node.get("data-resrch") or node.get("data-researchareas")
        if data_res:
            raw_items = re.split(r"[,;•|]", data_res)
            interests = [item.strip() for item in raw_items if item.strip() and len(item.strip()) <= 60]

        if not interests:
            interests = self._extract_interests_from_text(text_content)

        if not interests:
            bio_node = node.find(class_=re.compile(r"bio|research|interests|areas", re.I))
            if bio_node:
                bio_text = bio_node.get_text(separator=" ", strip=True)
                interests = self._extract_interests_from_text(bio_text)
                if not interests and len(bio_text) < 120:
                    interests = [i.strip() for i in re.split(r"[,;•\n]", bio_text) if i.strip() and len(i.strip()) <= 60]

        # Lab URL or Scholar URL if already present on card
        scholar_url: str | None = None
        lab_url: str | None = node.get("data-personallink")

        for a_tag in node.find_all("a", href=True):
            href = a_tag["href"]
            if "scholar.google.com" in href:
                scholar_url = href
            elif any(k in a_tag.get_text().lower() for k in ("lab", "group", "homepage", "website")):
                lab_url = urljoin(base_url, href)

        email_status = VerificationStatus.VERIFIED if email else VerificationStatus.UNVERIFIED

        prov = SourceProvenance(
            source_url=base_url,
            source_name="faculty_directory",
            snippet=f"Discovered in faculty directory: {name}",
            verification_status=VerificationStatus.VERIFIED,
        )

        return Professor(
            name=name,
            title=title,
            department=default_dept,
            institution=institution,
            email=email,
            email_status=email_status,
            profile_url=profile_url,
            lab_url=lab_url,
            scholar_url=scholar_url,
            research_interests=interests,
            sources=[prov],
        )

    def _parse_table_layout(
        self,
        soup: BeautifulSoup,
        base_url: str,
        institution: str,
        default_dept: str | None,
    ) -> list[Professor]:
        """Extract faculty from tables containing person listings."""
        professors: list[Professor] = []
        seen: set[str] = set()

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue

                row_text = row.get_text(separator=" ", strip=True)
                link = row.find("a", href=True)
                if not link:
                    continue

                name = clean_name(link.get_text(strip=True))
                if len(name.split()) < 2 or len(name) > 60 or name.lower() in seen:
                    continue

                seen.add(name.lower())
                profile_url = urljoin(base_url, link["href"])

                title: str | None = None
                for pat in TITLE_PATTERNS:
                    m = pat.search(row_text)
                    if m:
                        title = m.group(0).strip()
                        break
                title = clean_title(title)

                email: str | None = None
                mailto = row.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
                if mailto and mailto.get("href"):
                    raw_email = mailto["href"].split(":", 1)[1].split("?")[0].strip()
                    if EMAIL_REGEX.match(raw_email):
                        email = raw_email
                if not email:
                    em_match = EMAIL_REGEX.search(row_text)
                    if em_match:
                        email = em_match.group(0)

                interests = self._extract_interests_from_text(row_text)

                prov = SourceProvenance(
                    source_url=base_url,
                    source_name="faculty_directory",
                    snippet=f"Discovered in directory table: {name}",
                    verification_status=VerificationStatus.VERIFIED,
                )

                professors.append(
                    Professor(
                        name=name,
                        title=title,
                        department=default_dept,
                        institution=institution,
                        email=email,
                        email_status=VerificationStatus.VERIFIED if email else VerificationStatus.UNVERIFIED,
                        profile_url=profile_url,
                        research_interests=interests,
                        sources=[prov],
                    )
                )

        return professors

    def _parse_heading_list_layout(
        self,
        soup: BeautifulSoup,
        base_url: str,
        institution: str,
        default_dept: str | None,
    ) -> list[Professor]:
        """Extract faculty from heading-driven structures."""
        professors: list[Professor] = []
        seen: set[str] = set()

        for h in soup.find_all(["h2", "h3", "h4"]):
            link = h.find("a", href=True)
            if not link:
                continue
            name = clean_name(link.get_text(strip=True))
            if len(name.split()) < 2 or len(name) > 60 or name.lower() in seen:
                continue

            profile_url = urljoin(base_url, link["href"])

            # Check next siblings for title/email/research
            sibling_text = ""
            sib = h.find_next_sibling()
            count = 0
            while sib and count < 3 and sib.name not in ["h2", "h3", "h4"]:
                sibling_text += " " + sib.get_text(separator=" ", strip=True)
                sib = sib.find_next_sibling()
                count += 1

            title: str | None = None
            for pat in TITLE_PATTERNS:
                m = pat.search(sibling_text)
                if m:
                    title = m.group(0).strip()
                    break
            title = clean_title(title)

            email: str | None = None
            em_match = EMAIL_REGEX.search(sibling_text)
            if em_match:
                email = em_match.group(0)

            interests = self._extract_interests_from_text(sibling_text)
            seen.add(name.lower())

            prov = SourceProvenance(
                source_url=base_url,
                source_name="faculty_directory",
                snippet=f"Discovered in directory listing: {name}",
                verification_status=VerificationStatus.VERIFIED,
            )

            professors.append(
                Professor(
                    name=name,
                    title=title,
                    department=default_dept,
                    institution=institution,
                    email=email,
                    email_status=VerificationStatus.VERIFIED if email else VerificationStatus.UNVERIFIED,
                    profile_url=profile_url,
                    research_interests=interests,
                    sources=[prov],
                )
            )

        return professors

    def _enrich_from_profile(self, prof: Professor) -> Professor:
        """Fetch individual profile page to extract scholar links, lab links, and interests."""
        if not prof.profile_url:
            return prof

        response = self.client.get(prof.profile_url)
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        # 1. Google Scholar Link
        if not prof.scholar_url:
            scholar_tag = soup.find("a", href=re.compile(r"scholar\.google\.[a-z.]+/citations", re.IGNORECASE))
            if scholar_tag and scholar_tag.get("href"):
                prof.scholar_url = scholar_tag["href"]

        # 2. Lab or Personal Website
        if not prof.lab_url:
            for link in soup.find_all("a", href=True):
                href = link["href"]
                link_text = link.get_text().lower()
                if any(k in link_text for k in ("lab website", "research group", "homepage", "personal website", "lab page")):
                    if href.startswith("http") and "scholar.google" not in href:
                        prof.lab_url = href
                        break

        # 3. Email if missing
        if not prof.email:
            mailto = soup.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
            if mailto and mailto.get("href"):
                raw_email = mailto["href"].split(":", 1)[1].split("?")[0].strip()
                if EMAIL_REGEX.match(raw_email):
                    prof.email = raw_email
                    prof.email_status = VerificationStatus.VERIFIED
            else:
                em_match = EMAIL_REGEX.search(text)
                if em_match:
                    prof.email = em_match.group(0)
                    prof.email_status = VerificationStatus.VERIFIED

        # 4. Detailed Research Interests
        more_interests = self._extract_detailed_interests(soup)
        if more_interests:
            existing = set(i.lower() for i in prof.research_interests)
            for item in more_interests:
                if item.lower() not in existing:
                    prof.research_interests.append(item)

        # Attach provenance
        prof.sources.append(
            SourceProvenance(
                source_url=prof.profile_url,
                source_name="faculty_profile",
                snippet=f"Enriched profile data from {prof.profile_url}",
                verification_status=VerificationStatus.VERIFIED,
            )
        )

        return prof

    def _extract_interests_from_text(self, text: str) -> list[str]:
        """Extract comma/semicolon delimited interest list from labeled text."""
        match = re.search(
            r"(?:research\s+(?:interests?|areas?)|areas?\s+of\s+(?:interest|research)|specialization|focus)\s*[:\-–]\s*([^\.\n\r]+)",
            text,
            re.IGNORECASE,
        )
        if not match:
            return []

        raw_items = re.split(r"[,;•|]", match.group(1))
        interests = [item.strip() for item in raw_items if item.strip() and len(item.strip()) <= 60]
        return interests[:8]

    def _extract_detailed_interests(self, soup: BeautifulSoup) -> list[str]:
        """Extract research interests from section headers in individual profile pages."""
        for heading in soup.find_all(["h2", "h3", "h4", "strong"]):
            htext = heading.get_text(strip=True).lower()
            if any(term in htext for term in ("research interest", "research area", "research focus", "areas of specialization")):
                # Check for bullet points in next list
                parent = heading.parent
                ul = parent.find("ul") or heading.find_next_sibling("ul")
                if ul:
                    items = [li.get_text(strip=True) for li in ul.find_all("li") if li.get_text(strip=True)]
                    if items:
                        return items[:10]

                # Check following paragraph
                p = heading.find_next_sibling("p")
                if p:
                    text = p.get_text(strip=True)
                    if text:
                        raw_items = re.split(r"[,;•\n]", text)
                        return [item.strip() for item in raw_items if item.strip() and len(item.strip()) <= 60][:8]

        return []

    def _filter_and_rank_by_keywords(
        self,
        professors: list[Professor],
        keywords: list[str],
    ) -> list[Professor]:
        """Rank professors based on keyword overlap with research interests and bio."""
        scored: list[tuple[float, Professor]] = []
        kw_lower = [k.lower().strip() for k in keywords if k.strip()]

        for prof in professors:
            score = 0.0
            searchable_text = " ".join(
                [prof.name, prof.title or "", prof.department or ""] + prof.research_interests
            ).lower()

            for kw in kw_lower:
                if kw in searchable_text:
                    score += 1.0
                # Extra boost if explicitly in research interests list
                if any(kw in interest.lower() for interest in prof.research_interests):
                    score += 1.5

            scored.append((score, prof))

        # Sort descending by score
        scored.sort(key=lambda x: x[0], reverse=True)
        return [prof for _, prof in scored]
