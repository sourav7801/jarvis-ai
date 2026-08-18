"""Citation-first public-web search and bounded website reading.

Search prefers authoritative vertical sources, then configured Brave Search,
then Firecrawl's public keyless search tier. Wikipedia and current-news
discovery remain final fallbacks. Explicit public URLs can always be read
through the governed retriever when the site permits ordinary HTTP access.
"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from config import BRAVE_SEARCH_API_KEY, WEB_RESEARCH_STATE_FILE
from omni.runtime import audit_event
from omni.web_research import GovernedWebRetriever, WebDocument, WebPolicy, cite


URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
CURRENT_MARKERS = frozenset(
    {"current", "latest", "news", "today", "recent", "now", "update", "2026"}
)
LOCAL_SEARCH_MARKERS = frozenset({"file", "files", "folder", "folders", "download", "downloads", "computer", "laptop"})
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def is_web_request(text: str) -> bool:
    value = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    value = re.sub(r"\bwebber\b", "web", value)
    if URL_PATTERN.search(value):
        return True
    words = set(re.findall(r"[a-z0-9]+", value))
    if words.intersection(LOCAL_SEARCH_MARKERS) and re.search(r"\b(?:find|search|locate)\b", value):
        return False
    phrases = (
        "search the web", "search online", "find online", "find on the web",
        "read this website", "read this webpage", "read this url", "open and read",
        "web research", "research online", "look up online", "find websites",
    )
    if any(phrase in value for phrase in phrases):
        return True
    public_platform = re.search(
        r"\b(?:linkedin|youtube|spotify|instagram|github|x\.com|twitter|website|web)\b",
        value,
    )
    if public_platform and re.search(r"\b(?:search|find|look\s*up|check|who|profile)\b", value):
        return True
    if re.search(r"\b(?:current(?:ly)?|latest|trending|viral|today|right now)\b", value) and re.search(
        r"\b(?:song|music|artist|video|movie|show|trend|ranking|rank|profile|person|company|product|price|release)\b",
        value,
    ):
        return True
    value = re.sub(r"^jarvis[\s,:-]*", "", value)
    return bool(
        re.match(r"^(?:search|google|look up|research)\b", value)
        or re.match(r"^(?:top|best)\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b", value)
    )


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _json_request(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
    maximum: int = 2_000_000,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "OMNI-JARVIS-Web-Intelligence/1.0",
            **(headers or {}),
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Search response exceeded the configured byte limit.")
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("Search provider returned an invalid response.")
    return payload


def _post_json_request(
    url: str,
    body: dict[str, Any],
    timeout: float = 30.0,
    maximum: int = 4_000_000,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "OMNI-JARVIS-Web-Intelligence/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Search response exceeded the configured byte limit.")
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("Search provider returned an invalid response.")
    return payload


def _text_request(url: str, timeout: float = 20.0, maximum: int = 4_000_000) -> str:
    request = urllib.request.Request(
        url,
        headers={"Accept": "text/html", "User-Agent": "OMNI-JARVIS-Web-Intelligence/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Official ranking response exceeded the configured byte limit.")
    return raw.decode("utf-8", errors="replace")


class BraveSearch:
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str = "", requester: Callable = _json_request):
        self.api_key = str(api_key or "").strip()
        self.requester = requester

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        parameters = urllib.parse.urlencode(
            {"q": query[:400], "count": min(max(limit, 1), 20), "country": "IN", "search_lang": "en"}
        )
        payload = self.requester(
            f"{self.endpoint}?{parameters}",
            {"X-Subscription-Token": self.api_key},
        )
        results = payload.get("web", {}).get("results", [])
        return [
            {
                "title": _strip_html(item.get("title", "")),
                "url": str(item.get("url", "")).strip(),
                "excerpt": _strip_html(item.get("description", "")),
                "provider": "BRAVE_SEARCH",
            }
            for item in results[:limit]
            if isinstance(item, dict) and str(item.get("url", "")).startswith(("http://", "https://"))
        ]


class WikipediaSearch:
    endpoint = "https://en.wikipedia.org/w/api.php"

    def __init__(self, requester: Callable = _json_request):
        self.requester = requester

    def search(self, query: str, limit: int = 6) -> list[dict[str, Any]]:
        parameters = urllib.parse.urlencode(
            {
                "action": "query", "list": "search", "srsearch": query[:300],
                "srlimit": min(max(limit, 1), 10), "utf8": "1", "format": "json",
            }
        )
        payload = self.requester(f"{self.endpoint}?{parameters}")
        results = payload.get("query", {}).get("search", [])
        output = []
        for item in results[:limit]:
            if not isinstance(item, dict):
                continue
            title = _strip_html(item.get("title", ""))
            if not title:
                continue
            output.append(
                {
                    "title": title,
                    "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                    "excerpt": _strip_html(item.get("snippet", "")),
                    "provider": "WIKIPEDIA",
                }
            )
        return output


class FirecrawlKeylessSearch:
    """Broad public search with no account, key, or local credential."""

    endpoint = "https://api.firecrawl.dev/v2/search"

    def __init__(self, requester: Callable = _post_json_request):
        self.requester = requester

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        count = min(max(int(limit), 1), 10)
        payload = self.requester(
            self.endpoint,
            {"query": query[:400], "limit": count, "country": "IN"},
        )
        data = payload.get("data") or {}
        results = data.get("web") if isinstance(data, dict) else data
        if not isinstance(results, list):
            results = payload.get("results") or []
        output = []
        for item in results[:count]:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                continue
            output.append(
                {
                    "title": _strip_html(item.get("title") or url),
                    "url": url,
                    "excerpt": _strip_html(
                        item.get("description") or item.get("snippet") or item.get("summary") or ""
                    )[:1_200],
                    "provider": "FIRECRAWL_FREE",
                }
            )
        return output


class _NirfTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.table_depth = 0
        self.target_depth = 0
        self.in_row = False
        self.in_cell = False
        self.cell_text: list[str] = []
        self.cells: list[str] = []
        self.pdf_url = ""
        self.rows: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table":
            self.table_depth += 1
            if attributes.get("id") == "tbl_overall":
                self.target_depth = self.table_depth
        if not self.target_depth or self.table_depth != self.target_depth:
            return
        if tag == "tr":
            self.in_row = True
            self.cells = []
            self.pdf_url = ""
        elif tag == "td" and self.in_row:
            self.in_cell = True
            self.cell_text = []
        elif tag == "a" and self.in_cell:
            href = str(attributes.get("href") or "")
            if "/pdf/Management/" in href:
                self.pdf_url = href

    def handle_data(self, data: str) -> None:
        if self.in_cell and self.table_depth == self.target_depth:
            self.cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.target_depth and self.table_depth == self.target_depth:
            if tag == "td" and self.in_cell:
                self.cells.append(re.sub(r"\s+", " ", " ".join(self.cell_text)).strip())
                self.in_cell = False
            elif tag == "tr" and self.in_row:
                if len(self.cells) >= 6 and self.cells[0].startswith("IR-M-"):
                    try:
                        rank = int(self.cells[-1])
                        score = float(self.cells[-2])
                    except (TypeError, ValueError):
                        pass
                    else:
                        clean_name = re.sub(
                            r"\s+More Details\s+Close(?:\s*\|\s*)*$",
                            "",
                            self.cells[1],
                            flags=re.IGNORECASE,
                        ).strip()
                        self.rows.append(
                            {
                                "institute_id": self.cells[0],
                                "name": clean_name,
                                "city": self.cells[2],
                                "state": self.cells[3],
                                "score": score,
                                "rank": rank,
                                "pdf_url": urllib.parse.urljoin(
                                    "https://www.nirfindia.org/", self.pdf_url
                                ) if self.pdf_url else "",
                            }
                        )
                self.in_row = False
        if tag == "table":
            if self.table_depth == self.target_depth:
                self.target_depth = 0
            self.table_depth = max(self.table_depth - 1, 0)


class IndiaOfficialRankingSearch:
    """Resolve IIM ranking questions against the latest official NIRF table."""

    template = "https://www.nirfindia.org/Rankings/{year}/ManagementRanking.html"

    def __init__(self, requester: Callable = _text_request, now: Callable[[], datetime] | None = None):
        self.requester = requester
        self.now = now or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def supports(query: str) -> bool:
        value = query.lower()
        institution = "iim" in value or "indian institute of management" in value
        ranking = any(term in value for term in ("rank", "top", "best"))
        return institution and ranking

    def search(self, query: str, limit: int = 5) -> dict[str, Any] | None:
        if not self.supports(query):
            return None
        current_year = self.now().year
        html_text = ""
        ranking_url = ""
        year = current_year
        for candidate in range(current_year, current_year - 3, -1):
            try:
                ranking_url = self.template.format(year=candidate)
                html_text = self.requester(ranking_url)
                if "tbl_overall" in html_text:
                    year = candidate
                    break
            except Exception:
                continue
        if not html_text:
            return None
        parser = _NirfTableParser()
        parser.feed(html_text)
        rows = sorted(
            (row for row in parser.rows if "indian institute of management" in row["name"].lower()),
            key=lambda row: row["rank"],
        )[: min(max(int(limit), 1), 10)]
        if not rows:
            return None
        sources = [
            {
                "title": f"#{row['rank']} - {row['name']}",
                "url": row["pdf_url"] or ranking_url,
                "excerpt": (
                    f"Official NIRF {year} Management rank {row['rank']}; "
                    f"score {row['score']:.2f}; {row['city']}, {row['state']}."
                ),
                "provider": "NIRF_GOV_IN",
                "read_status": "OFFICIAL_RANKING",
            }
            for row in rows
        ]
        answer = "According to the official NIRF " + str(year) + " Management ranking: " + "; ".join(
            f"{row['rank']}. {row['name']} ({row['city']}, score {row['score']:.2f})" for row in rows
        ) + "."
        return {"year": year, "ranking_url": ranking_url, "sources": sources, "answer": answer}


def _extract_query(text: str) -> str:
    value = URL_PATTERN.sub(" ", str(text or ""))
    value = re.sub(
        r"^(?:(?:hi|hello|hey)\s+)?jarvis[\s,:-]*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"^(?:can|could|would)\s+you\s+", "", value, flags=re.IGNORECASE)
    platform_match = re.match(
        r"^(?:please\s+)?(?:search|find|look\s*up|check)\s+(?:for\s+)?(?:on\s+)?"
        r"(linkedin|youtube|spotify|instagram|github|twitter|x\.com)\b[\s,:?-]*(.*)$",
        value,
        flags=re.IGNORECASE,
    )
    if platform_match:
        platform, subject = platform_match.groups()
        value = f"{subject.strip()} {platform}".strip()
    value = re.sub(
        r"^(?:please\s+)?(?:search(?:(?: the)? web| online)?(?: for)?|google|find (?:online|on the web)(?: information)?(?: about| on| for)?|web research|research(?: online)?|look up(?: online)?)(?:\s+for)?\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"^(?:top|first)\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\b(?:on\s+)?webber\b", "web", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip(" ,.;:-")[:400]


def _requested_limit(text: str, default: int = 6) -> int:
    value = str(text or "").lower()
    match = re.search(
        r"\b(?:top|first|show|give|find|list)\s+(?:me\s+)?(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
        value,
    )
    if not match:
        match = re.search(r"\b(\d+)\s+(?:results?|sources?|websites?|links?)\b", value)
    if not match:
        return min(max(int(default), 1), 10)
    raw = match.group(1)
    count = int(raw) if raw.isdigit() else NUMBER_WORDS.get(raw, default)
    return min(max(count, 1), 10)


def _relevant_excerpt(document: WebDocument, query: str, maximum: int = 900) -> str:
    text = re.sub(r"\s+", " ", document.text).strip()
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    terms = {item for item in re.findall(r"[a-z0-9]+", query.lower()) if len(item) > 2}
    ranked = sorted(
        enumerate(sentences[:2_000]),
        key=lambda item: (
            -sum(term in item[1].lower() for term in terms),
            item[0],
        ),
    )
    selected = [sentence.strip() for _index, sentence in ranked[:5] if sentence.strip()]
    excerpt = " ".join(selected) or text[:maximum]
    return excerpt[:maximum].rsplit(" ", 1)[0] if len(excerpt) > maximum else excerpt


class WebIntelligenceAgent:
    def __init__(
        self,
        state_path: Path | str | None = None,
        retriever: GovernedWebRetriever | None = None,
        brave: BraveSearch | None = None,
        wikipedia: WikipediaSearch | None = None,
        firecrawl: FirecrawlKeylessSearch | None = None,
        official_rankings: IndiaOfficialRankingSearch | None = None,
        news_search: Callable | None = None,
    ) -> None:
        self.state_path = Path(state_path or WEB_RESEARCH_STATE_FILE)
        self.retriever = retriever or GovernedWebRetriever(
            WebPolicy(max_response_bytes=2_000_000, timeout_seconds=20.0, max_redirects=5)
        )
        self.brave = brave or BraveSearch(BRAVE_SEARCH_API_KEY)
        self.wikipedia = wikipedia or WikipediaSearch()
        self.firecrawl = firecrawl or FirecrawlKeylessSearch()
        self.official_rankings = official_rankings or IndiaOfficialRankingSearch()
        self.news_search = news_search
        self._lock = RLock()
        self._state: dict[str, Any] = {
            "version": 2,
            "latest": None,
            "history": [],
            "recent_results": [],
        }
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._state.update(payload)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.state_path)

    def _remember(self, result: dict[str, Any]) -> None:
        summary = {
            "query": result.get("query"), "mode": result.get("mode"),
            "success": result.get("success"), "source_count": len(result.get("sources", [])),
            "timestamp": result.get("timestamp"),
        }
        durable_result = {
            key: value for key, value in result.items()
            if key != "message"
        }
        with self._lock:
            self._state["version"] = 2
            self._state["latest"] = result
            self._state["history"] = ([summary] + list(self._state.get("history", [])))[:25]
            self._state["recent_results"] = (
                [durable_result] + list(self._state.get("recent_results", []))
            )[:10]
            self._save()

    @staticmethod
    def _source_from_document(document: WebDocument, query: str) -> dict[str, Any]:
        excerpt = _relevant_excerpt(document, query)
        citation = cite(document, excerpt or document.title)
        return {
            "title": citation.title,
            "url": citation.url,
            "excerpt": citation.excerpt,
            "retrieved_at": citation.retrieved_at,
            "checksum": citation.source_checksum,
            "provider": "DIRECT_WEBSITE",
            "read_status": "EXTRACTED",
        }

    def _read_urls(self, urls: list[str], query: str) -> tuple[list[dict[str, Any]], list[str]]:
        sources: list[dict[str, Any]] = []
        errors: list[str] = []
        for url in urls[:5]:
            try:
                sources.append(self._source_from_document(self.retriever.fetch(url), query))
            except Exception as error:
                errors.append(f"{url}: {type(error).__name__}")
        return sources, errors

    def assess_source(
        self,
        source: dict[str, Any],
        request: str,
        *,
        selection_index: int = 1,
        origin_query: str = "",
    ) -> dict[str, Any]:
        """Assess one previously retrieved public profile using job-relevant evidence only.

        This is intentionally decision support, not an automated hiring verdict. It
        never infers protected traits and always records the evidence gaps that need
        an interview, references, or work samples.
        """

        url = str(source.get("url") or "").strip()
        if not URL_PATTERN.fullmatch(url):
            raise ValueError("The selected result does not contain a valid public URL.")
        text = re.sub(r"\s+", " ", str(request or "")).strip()
        if len(text) < 4 or len(text) > 4_000:
            raise ValueError("Assessment request must be between 4 and 4,000 characters.")

        timestamp = datetime.now(timezone.utc).isoformat()
        errors: list[str] = []
        selected = dict(source)
        read_sources, read_errors = self._read_urls([url], text)
        if read_sources:
            selected = read_sources[0]
        errors.extend(read_errors)

        title = str(selected.get("title") or source.get("title") or "Selected public profile").strip()
        excerpt = re.sub(
            r"\s+",
            " ",
            str(selected.get("excerpt") or source.get("excerpt") or ""),
        ).strip()
        evidence_text = f"{title} {excerpt}".lower()
        evidence: list[str] = []
        if re.search(r"\b(?:strategy|consulting|consultant|transformation)\b", evidence_text):
            evidence.append("The public profile claims strategy, consulting, or business-transformation exposure.")
        if re.search(r"\b(?:mba|management|sjmsom|business school)\b", evidence_text):
            evidence.append("The public profile claims formal management or MBA education.")
        if re.search(r"\b(?:software|engineer|technology|technical|developer|data)\b", evidence_text):
            evidence.append("The public profile claims technical, software, or data experience.")
        if re.search(r"\b(?:finance|accounting|financial)\b", evidence_text):
            evidence.append("The public profile claims finance or accounting exposure.")
        if re.search(r"\b(?:lead|leader|manager|managed|founder|head|director)\b", evidence_text):
            evidence.append("The public profile contains a leadership or management claim that should be verified.")
        if not evidence:
            evidence.append("The selected public result provides only limited professional-profile evidence.")

        gaps = [
            "The role, authority level, objectives, and success metrics for your company were not specified.",
            "The public page does not verify measurable outcomes, team size, budget or P&L ownership, or decision authority.",
            "Work samples, structured interview evidence, references, and identity/employment verification are still required.",
        ]
        answer = (
            f"Preliminary assessment of result {selection_index}, {title}: promising signals may exist, "
            "but there is not enough verified, role-specific evidence to decide that this person can handle your company. "
            f"Evidence available: {' '.join(evidence)} "
            "Recommendation: treat this as a shortlist lead only. Define the exact role, then use a structured interview, "
            "work-sample exercise, reference checks, and verification of claimed experience before making any hiring or leadership decision."
        )
        notice = (
            "Assessment is limited to job-relevant information in one public result. JARVIS does not infer protected "
            "personal traits or make an automatic hire/no-hire decision. Login-only or unavailable profile details are not invented."
        )
        result = {
            "success": True,
            "type": "web_intelligence",
            "action": "open_web",
            "mode": "SOURCE_ASSESSMENT",
            "query": text,
            "origin_query": str(origin_query or ""),
            "timestamp": timestamp,
            "providers": [str(selected.get("provider") or source.get("provider") or "PUBLIC_WEB")],
            "broad_search_configured": self.brave.configured,
            "requested_limit": 1,
            "answer": answer,
            "assessment": {
                "selection_index": selection_index,
                "subject": title,
                "url": url,
                "verdict": "ROLE_SPECIFIC_EVIDENCE_REQUIRED",
                "confidence": "LOW",
                "evidence": evidence,
                "gaps": gaps,
                "prohibited_inferences": "PROTECTED_TRAITS_NOT_USED",
                "recommended_next_step": "STRUCTURED_ROLE_INTERVIEW_AND_VERIFICATION",
            },
            "sources": [selected],
            "errors": errors[:10],
            "notice": notice,
        }
        result["message"] = self._message(result)
        self._remember(result)
        audit_event(
            "web_intelligence",
            "source_assessment",
            "SUCCEEDED",
            {"selection_index": selection_index, "source_count": 1},
        )
        return result

    def _keyless_news(self, query: str, limit: int) -> list[dict[str, Any]]:
        search = self.news_search
        if search is None:
            try:
                from workstation.market_news import search_market_news
                search = search_market_news
            except Exception:
                return []
        try:
            payload = search(query, limit=limit, timespan="3d")
        except Exception:
            return []
        return [
            {
                "title": str(item.get("title", "")),
                "url": str(item.get("url", "")),
                "excerpt": "Current-news discovery result; open the linked source for article text.",
                "retrieved_at": str(item.get("seen_date", "")),
                "checksum": "",
                "provider": str(payload.get("source", "NEWS_DISCOVERY")),
                "read_status": "HEADLINE_ONLY",
            }
            for item in payload.get("articles", [])[:limit]
            if isinstance(item, dict) and item.get("url")
        ]

    @staticmethod
    def _message(result: dict[str, Any]) -> str:
        sources = result.get("sources", [])
        if not sources:
            return str(result.get("notice") or "No public source could be retrieved.")
        answer = str(result.get("answer") or "").strip()
        lines = [
            answer or f"Web Intelligence found {len(sources)} citable source{'s' if len(sources) != 1 else ''} for: {result['query']}",
            "",
        ]
        for index, source in enumerate(sources[:10], start=1):
            excerpt = re.sub(r"\s+", " ", str(source.get("excerpt") or "")).strip()
            lines.append(f"{index}. {source.get('title') or source.get('url')}")
            if excerpt:
                lines.append(f"   {excerpt[:500]}")
            lines.append(f"   Source: {source.get('url')}")
        lines.extend(["", str(result.get("notice") or "")])
        return "\n".join(lines).strip()

    def research(self, request: str) -> dict[str, Any]:
        text = re.sub(r"\s+", " ", str(request or "")).strip()
        if len(text) < 4 or len(text) > 4_000:
            raise ValueError("Web request must be between 4 and 4,000 characters.")
        urls = [item.rstrip(".,);]") for item in URL_PATTERN.findall(text)][:5]
        query = _extract_query(text) or (urls[0] if urls else text[:400])
        requested_limit = _requested_limit(text, 5 if urls else 6)
        timestamp = datetime.now(timezone.utc).isoformat()
        sources: list[dict[str, Any]] = []
        errors: list[str] = []
        providers: list[str] = []
        answer = ""

        if urls:
            sources, errors = self._read_urls(urls, query)
            providers.append("DIRECT_WEBSITE")
            mode = "READ_URL"
            notice = (
                "Content was extracted from public HTTP responses. Dynamic, login-only, paywalled, "
                "or blocked text is not invented."
            )
        else:
            mode = "WEB_SEARCH"
            try:
                official = self.official_rankings.search(text, requested_limit)
            except Exception as error:
                official = None
                errors.append(f"OFFICIAL_RANKING: {type(error).__name__}")
            if official:
                mode = "OFFICIAL_RANKING"
                providers.append("NIRF_GOV_IN")
                sources.extend(official["sources"])
                answer = str(official["answer"])
                notice = (
                    f"JARVIS recognized a ranking question and automatically used the latest available "
                    f"official Government of India NIRF Management table ({official['year']})."
                )
                search_results = []
            elif self.brave.configured:
                try:
                    search_results = self.brave.search(query, requested_limit)
                    providers.append("BRAVE_SEARCH")
                except Exception as error:
                    search_results = []
                    errors.append(f"BRAVE_SEARCH: {type(error).__name__}")
            else:
                try:
                    search_results = self.firecrawl.search(query, requested_limit)
                    if search_results:
                        providers.append("FIRECRAWL_FREE")
                except Exception as error:
                    search_results = []
                    errors.append(f"FIRECRAWL_FREE: {type(error).__name__}")
            if sources:
                pass
            elif search_results:
                read_sources, read_errors = self._read_urls(
                    [item["url"] for item in search_results[: min(3, requested_limit)]], query
                )
                read_by_url = {item["url"]: item for item in read_sources}
                for item in search_results[:requested_limit]:
                    sources.append(
                        read_by_url.get(
                            item["url"],
                            {
                                **item,
                                "retrieved_at": timestamp,
                                "checksum": "",
                                "read_status": "SEARCH_SNIPPET",
                            },
                        )
                    )
                errors.extend(read_errors)
                if "BRAVE_SEARCH" in providers:
                    notice = (
                        "Broad web results came from the configured Brave Search API. Top public pages "
                        "were read when accessible; other entries remain clearly labelled search snippets."
                    )
                else:
                    notice = (
                        "Broad web results came from Firecrawl's public keyless search tier. JARVIS read "
                        "the top accessible pages automatically; the query is sent to that search provider."
                    )
            else:
                try:
                    wiki = self.wikipedia.search(query, requested_limit)
                    providers.append("WIKIPEDIA")
                except Exception as error:
                    wiki = []
                    errors.append(f"WIKIPEDIA: {type(error).__name__}")
                sources.extend(
                    {
                        **item,
                        "retrieved_at": timestamp,
                        "checksum": "",
                        "read_status": "SEARCH_SNIPPET",
                    }
                    for item in wiki
                )
                terms = set(re.findall(r"[a-z0-9]+", query.lower()))
                if terms.intersection(CURRENT_MARKERS):
                    current = self._keyless_news(query, max(1, requested_limit - len(sources)))
                    if current:
                        providers.append("CURRENT_NEWS")
                        sources.extend(current)
                notice = (
                    "Broad keyless search was unavailable, so JARVIS fell back to public Wikipedia"
                    + (" and current-news discovery" if "CURRENT_NEWS" in providers else "")
                    + ". You can also read any ordinary public page directly by providing its URL."
                )

        deduplicated: list[dict[str, Any]] = []
        seen = set()
        for source in sources:
            url = str(source.get("url", "")).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            deduplicated.append(source)
        result = {
            "success": bool(deduplicated),
            "type": "web_intelligence",
            "action": "open_web",
            "mode": mode,
            "query": query,
            "timestamp": timestamp,
            "providers": providers,
            "broad_search_configured": self.brave.configured,
            "requested_limit": requested_limit,
            "answer": answer,
            "sources": deduplicated[:requested_limit],
            "errors": errors[:10],
            "notice": notice,
        }
        result["message"] = self._message(result)
        self._remember(result)
        audit_event(
            "web_intelligence", "research", "SUCCEEDED" if result["success"] else "DEGRADED",
            {"mode": mode, "source_count": len(result["sources"]), "providers": providers},
        )
        return result

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            latest = self._state.get("latest")
            history = list(self._state.get("history", []))
            recent_results = list(self._state.get("recent_results", []))
        return {
            "version": 2,
            "latest": latest,
            "history": history,
            "recent_results": recent_results,
            "broad_search_configured": self.brave.configured,
            "capabilities": {
                "direct_public_url_reading": True,
                "bounded_text_extraction": True,
                "redirect_revalidation": True,
                "private_network_blocking": True,
                "citation_provenance": True,
                "keyless_search": "FIRECRAWL_FREE_WITH_WIKIPEDIA_FALLBACK",
                "broad_web_search": "BRAVE_SEARCH" if self.brave.configured else "FIRECRAWL_FREE",
                "official_india_rankings": "NIRF_GOV_IN",
            },
        }


WEB_INTELLIGENCE_AGENT = WebIntelligenceAgent()


def web_intelligence(text: str) -> dict[str, Any]:
    return WEB_INTELLIGENCE_AGENT.research(text)
