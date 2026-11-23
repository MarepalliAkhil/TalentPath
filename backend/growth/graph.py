"""The skill graph and curated learning links, both plain data in shared/ that a person reviews.

Learning paths respect prerequisites: a skill never appears before the skills it needs.
Links come only from shared/learning_links.json; a skill without one shows text only.
"""

import heapq
import json
from functools import lru_cache
from urllib.parse import urlparse

from django.conf import settings

EFFORT_ORDER = {"small": 0, "medium": 1, "large": 2}
EFFORT_LABELS = {"small": "Small", "medium": "Medium", "large": "Large"}


@lru_cache(maxsize=1)
def skill_graph() -> dict:
    with open(settings.SKILL_GRAPH_PATH, encoding="utf-8") as fh:
        return json.load(fh)["skills"]


@lru_cache(maxsize=1)
def learning_links() -> dict:
    with open(settings.LEARNING_LINKS_PATH, encoding="utf-8") as fh:
        links = json.load(fh)["links"]
    # Defensive: only https links survive, whatever is in the file.
    return {slug: entry for slug, entry in links.items() if urlparse(entry.get("url", "")).scheme == "https"}


def prerequisites(slug: str) -> list[str]:
    return list(skill_graph().get(slug, {}).get("prerequisites", []))


def related(slug: str) -> list[str]:
    return list(skill_graph().get(slug, {}).get("related", []))


def effort(slug: str) -> str | None:
    return skill_graph().get(slug, {}).get("effort")


def link_for(slug: str) -> dict | None:
    entry = learning_links().get(slug)
    return {"title": entry["title"], "url": entry["url"]} if entry else None


def learning_path(
    missing: list[str], have: set[str], *, priority: dict[str, int] | None = None
) -> list[dict]:
    """Order the missing skills (plus any prerequisites the person also lacks) so that every
    prerequisite comes first. Among skills that are ready, lower `priority` first (required
    before nice-to-have), then smaller effort, then the slug for a stable order."""
    priority = dict(priority or {})
    needed: dict[str, set[str]] = {}
    because: dict[str, set[str]] = {}

    def visit(slug: str, trail: tuple = ()):
        if slug in have or slug in trail:
            return
        if slug not in needed:
            needed[slug] = set()
        for pre in prerequisites(slug):
            if pre in have:
                continue
            needed[slug].add(pre)
            because.setdefault(pre, set()).add(slug)
            priority.setdefault(pre, priority.get(slug, 9))
            priority[pre] = min(priority[pre], priority.get(slug, 9))
            visit(pre, trail + (slug,))

    for slug in missing:
        visit(slug)

    indegree = {slug: len(pres & needed.keys()) for slug, pres in needed.items()}
    dependents: dict[str, list[str]] = {}
    for slug, pres in needed.items():
        for pre in pres:
            dependents.setdefault(pre, []).append(slug)

    def key(slug):
        return (priority.get(slug, 9), EFFORT_ORDER.get(effort(slug) or "medium", 1), slug)

    ready = [key(s) for s, d in indegree.items() if d == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        _, _, slug = heapq.heappop(ready)
        order.append(slug)
        for nxt in dependents.get(slug, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                heapq.heappush(ready, key(nxt))
    # A cycle in the data would leave skills out; add them at the end rather than lose them.
    order += sorted(s for s in needed if s not in order)
    return [
        {
            "slug": slug,
            "effort": effort(slug),
            "effort_label": EFFORT_LABELS.get(effort(slug) or "", "Not rated"),
            "prerequisites": [p for p in prerequisites(slug) if p in needed],
            "unlocks": sorted(because.get(slug, set())),
            "link": link_for(slug),
        }
        for slug in order
    ]
