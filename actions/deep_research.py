"""Autonomous Deep Web Research.
Created and developed by Sajan Rai for Zaya.
Multi-step web research with query decomposition, source collection,
deduplication, relevance ranking, fact synthesis, and knowledge store integration.
"""
from __future__ import annotations

import json
import hashlib
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse

import requests

from core.execution_policy import require_owner
from core.tool_result import ToolResult

logger = logging.getLogger("actions.deep_research")


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def search_web_sources(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Executes web search and returns normalized sources.

    Returns an EMPTY list when the backend is unavailable. It never invents a
    placeholder citation: the old fallback appended a "Intelligence Summary"
    row whose snippet was a generic sentence and whose URL was a search
    redirect, and the report then presented it as one of N "verified
    reference points". A report that admits it found nothing is worth more
    than one that quietly makes things up.
    """
    results = []
    # 1. Try DuckDuckGo HTML search
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        encoded = urllib.parse.quote(query)
        resp = requests.get(f"https://html.duckduckgo.com/html/?q={encoded}", headers=headers, timeout=8)
        if resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select(".result__snippet")[:max_results]:
                parent = a.find_parent(class_="result")
                title_elem = parent.select_one(".result__title") if parent else None
                url_elem = parent.select_one(".result__url") if parent else None
                title = title_elem.get_text(strip=True) if title_elem else "Search Result"
                link_elem = parent.select_one('a.result__a') if parent else None
                raw_url = (link_elem.get('href', '') if link_elem else
                           (url_elem.get('href', '') if url_elem else ''))
                if raw_url.startswith('//'):
                    raw_url = 'https:' + raw_url
                if 'duckduckgo.com/l/' in raw_url:
                    raw_url = urllib.parse.parse_qs(urllib.parse.urlsplit(raw_url).query).get('uddg', [''])[0]
                if raw_url and not raw_url.startswith("http"):
                    raw_url = f"https://{raw_url}"
                if not raw_url or urllib.parse.urlsplit(raw_url).scheme not in {'http', 'https'}:
                    continue
                snippet = a.get_text(strip=True)
                results.append({"title": title, "url": raw_url, "snippet": snippet})
    except Exception as e:
        logger.debug(f"DuckDuckGo search error: {e}")

    return results


def deduplicate_and_rank_sources(sources: List[Dict[str, str]], topic_terms: List[str]) -> List[Dict[str, str]]:
    """Deduplicates sources by normalized URL domain/path and ranks by topic relevance."""
    seen_urls = set()
    deduped = []

    for s in sources:
        url = s.get("url", "").strip()
        # Normalize url
        norm_url = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
        if norm_url in seen_urls:
            continue
        seen_urls.add(norm_url)

        # Relevance scoring based on title + snippet keyword match
        text = f"{s.get('title', '')} {s.get('snippet', '')}".lower()
        score = sum(1 for term in topic_terms if term in text)
        s["_score"] = score
        deduped.append(s)

    # Sort descending by relevance score
    deduped.sort(key=lambda x: x.get("_score", 0), reverse=True)
    for s in deduped:
        s.pop("_score", None)

    return deduped


def synthesize_research_report(topic: str, sources: List[Dict[str, str]]) -> str:
    """Synthesizes compiled facts into a structured Markdown research dossier."""
    citations = []
    findings = []

    if not sources:
        # Say plainly that nothing was retrieved rather than dressing an
        # empty run up as a summary.
        return f"""# Autonomous Deep Research Report: {topic}

## Executive Summary
No web sources could be retrieved for **{topic}** during this run. The search
backend was unavailable, rate-limited, or blocked, so no claims are made.

## Key Findings & Data
- No source claims were retrieved, so no findings are reported.

## Verification & Source Citations
| Source Title | Link |
| :--- | :--- |
| _No sources retrieved_ | — |

*Generated autonomously by Zaya Research Engine on {time.strftime('%Y-%m-%d %H:%M:%S')}.*
"""

    for i, s in enumerate(sources, 1):
        title = s.get("title", f"Source {i}")
        snippet = s.get("snippet", "")
        url = s.get("url", "")
        findings.append(f"### {i}. {title}\n{snippet}\n")
        citations.append(f"| [{i}] {title} | {url} |")

    citations_table = "\n".join(citations)
    findings_text = "\n".join(findings) if findings else "- No verified source claims found."

    return f"""# Autonomous Deep Research Report: {topic}

## Executive Summary
Compilation on **{topic}**, assembled from {len(sources)} retrieved source reference points.

## Key Findings & Data
{findings_text}

## Verification & Source Citations
| Source Title | Link |
| :--- | :--- |
{citations_table}

*Generated autonomously by Zaya Research Engine on {time.strftime('%Y-%m-%d %H:%M:%S')}.*
"""


def save_to_knowledge_base(topic: str, sources: List[Dict[str, str]]) -> int:
    """Saves synthesized findings to Zaya's SQLite FTS5 knowledge store."""
    saved_count = 0
    try:
        from memory.knowledge_store import get_knowledge_store
        ks = get_knowledge_store()
        # The knowledge store keys on (category, key) and overwrites on
        # conflict, so a truncated topic alone made two different research
        # runs clobber each other. A short digest of the full topic keeps
        # them apart.
        digest = hashlib.sha1(topic.encode("utf-8")).hexdigest()[:8]
        for i, s in enumerate(sources[:5]):
            key = f"{topic[:30]}_{digest}_ref_{i+1}".replace(" ", "_").lower()
            val = f"{s.get('title', '')}: {s.get('snippet', '')} (Source: {s.get('url', '')})"
            ks.set_fact(
                category="research",
                key=key,
                value=val,
                source="deep_research",
                confidence=0.9
            )
            saved_count += 1
    except Exception as e:
        logger.debug(f"Knowledge store integration notice: {e}")
    return saved_count


def run_deep_research_cycle(
    topic: str,
    depth: str = "standard",
    save_knowledge: bool = True,
    max_iterations: int = 3
) -> Dict[str, Any]:
    """Runs a complete bounded deep research cycle with progress tracking."""
    # 1. Decompose topic into sub-queries
    topic_terms = [t.lower() for t in re.findall(r"\w+", topic) if len(t) > 2]
    sub_queries = [topic]
    if depth in ("standard", "comprehensive"):
        sub_queries.append(f"{topic} specifications details")
    if depth == "comprehensive":
        sub_queries.append(f"{topic} comparison review")

    all_sources = []
    # Bounded iteration loop
    for q in sub_queries[:max_iterations]:
        collected = search_web_sources(q, max_results=4)
        all_sources.extend(collected)

    # 2. Deduplicate and rank
    ranked_sources = deduplicate_and_rank_sources(all_sources, topic_terms)

    # 3. Synthesize report
    report_md = synthesize_research_report(topic, ranked_sources)

    # 4. Save to docs/research/
    out_dir = get_base_dir() / "docs" / "research"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", topic.lower())[:40]
    out_path = out_dir / f"{slug}.md"
    out_path.write_text(report_md, encoding="utf-8")

    # 5. Persist into knowledge store
    saved_facts = 0
    if save_knowledge:
        saved_facts = save_to_knowledge_base(topic, ranked_sources)

    return {
        "status": "success",
        "topic": topic,
        "saved_path": str(out_path),
        "source_count": len(ranked_sources),
        "saved_facts": saved_facts,
        "report": report_md
    }


def deep_research(parameters: dict, **_kwargs) -> str:
    """Deep Research Action handler."""
    require_owner()
    topic = str(parameters.get("topic", "")).strip()
    if not topic:
        return json.dumps({"status": "error", "message": "Research topic cannot be empty."})

    depth = str(parameters.get("depth", "standard")).lower()
    save_knowledge = bool(parameters.get("save_knowledge", True))

    res = run_deep_research_cycle(topic, depth=depth, save_knowledge=save_knowledge)

    if res["source_count"] == 0:
        # No sources were retrieved. Report that honestly instead of
        # claiming a completed research cycle over invented citations.
        return json.dumps({
            "status": "partial",
            "topic": res["topic"],
            "saved_path": res["saved_path"],
            "summary": (
                f"Deep research could not retrieve any web sources for '{topic}' "
                f"(search backend unavailable or blocked). A report recording that "
                f"was written to {res['saved_path']}."
            ),
            "source_count": 0,
            "report": res["report"]
        }, indent=2)

    return json.dumps({
        "status": "success",
        "topic": res["topic"],
        "saved_path": res["saved_path"],
        "source_count": res["source_count"],
        "summary": f"Deep research completed: {res['source_count']} sources cited, {res['saved_facts']} facts saved to memory. Report written to {res['saved_path']}",
        "report": res["report"]
    }, indent=2)


TOOL = {
    "name": "deep_research",
    "description": "Autonomous Deep Web Research: Multimodal agentic crawler that researches topics, breakthroughs, codebases, or news, synthesizing reports with full source citations and saving insights into long-term knowledge.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "topic": {
                "type": "STRING",
                "description": "The exact subject or question to research deeply."
            },
            "depth": {
                "type": "STRING",
                "enum": ["quick", "standard", "comprehensive"],
                "description": "Research depth (default: standard)."
            },
            "save_knowledge": {
                "type": "BOOLEAN",
                "description": "Whether to store structured findings into Zaya's SQLite knowledge base (default: True)."
            }
        },
        "required": ["topic"]
    },
    "handler": deep_research
}
