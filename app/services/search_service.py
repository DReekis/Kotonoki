import html
import re
import time
from typing import Dict, Any, List, Optional
from sqlalchemy import func, or_, and_, select
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models import Dispatch, Branch, PenName

class SearchService:
    # In-memory search cache to absorb traffic spikes on popular keywords
    _cache: Dict[str, tuple] = {}
    _CACHE_TTL = 45  # seconds
    _MAX_CACHE_SIZE = 250

    @classmethod
    def parse_query(cls, raw: str) -> Dict[str, Optional[str]]:
        """
        Extract structured filters (@author, branch:slug or /slug) and remaining keywords.
        """
        if not raw:
            return {"keywords": "", "branch": None, "author": None}

        q = raw.strip()
        branch = None
        author = None

        # Extract branch:name or /name
        branch_match = re.search(r'(?:branch:|(?<=\s)/|^/)([a-z0-9-]+)', q, re.I)
        if branch_match:
            branch = branch_match.group(1).lower()
            q = q[:branch_match.start()] + " " + q[branch_match.end():]

        # Extract author:name or @name
        author_match = re.search(r'(?:author:|@)([a-zA-Z0-9_]+)', q)
        if author_match:
            author = author_match.group(1).lower()
            q = q[:author_match.start()] + " " + q[author_match.end():]

        keywords = " ".join(q.split())
        return {
            "keywords": keywords,
            "branch": branch,
            "author": author
        }

    @classmethod
    def highlight_excerpt(cls, html_content: str, keywords: str, max_length: int = 180) -> str:
        """
        Extract a readable excerpt surrounding the matched keyword with <mark> highlighting.
        """
        text = re.sub(r'<[^>]+>', ' ', html_content or '')
        text = " ".join(text.split())
        if not text:
            return ""

        words = [re.escape(w) for w in keywords.split() if len(w) > 1]
        if not words:
            snippet = text[:max_length]
            return html.escape(snippet) + ("..." if len(text) > max_length else "")

        try:
            pattern = re.compile(r'(' + '|'.join(words) + r')', re.I)
            match = pattern.search(text)
            if not match:
                snippet = text[:max_length]
                return html.escape(snippet) + ("..." if len(text) > max_length else "")

            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 120)
            snippet = text[start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."

            escaped = html.escape(snippet)
            return pattern.sub(r'<mark class="search-match">\1</mark>', escaped)
        except Exception:
            return html.escape(text[:max_length])

    @classmethod
    def search(
        cls,
        raw_query: str,
        filter_branch: Optional[str] = None,
        sort_by: str = "relevance",
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        High-performance indexed full-text search with query caching, branch/author scoping,
        and dialect-optimized PostgreSQL tsvector or SQLite token matching.
        """
        parsed = cls.parse_query(raw_query)
        keywords = parsed["keywords"]
        target_branch = filter_branch or parsed["branch"]
        target_author = parsed["author"]

        if not keywords and not target_branch and not target_author:
            return {
                "dispatches": [],
                "has_more": False,
                "page": 1,
                "parsed": parsed,
                "keywords": "",
                "target_branch": None,
                "target_author": None
            }

        # Check Cache
        cache_key = f"{keywords}|{target_branch}|{target_author}|{sort_by}|{page}|{page_size}"
        now = time.time()
        if cache_key in cls._cache:
            timestamp, cached_result = cls._cache[cache_key]
            if now - timestamp < cls._CACHE_TTL:
                return cached_result

        # Build base query with eager-loaded relationships (no N+1 queries)
        stmt = (
            select(Dispatch)
            .options(joinedload(Dispatch.branch), joinedload(Dispatch.author))
            .join(Branch, Dispatch.branch_id == Branch.id)
            .join(PenName, Dispatch.author_id == PenName.id)
        )

        conditions = []

        # 1. Branch filter
        if target_branch:
            conditions.append(Branch.slug == target_branch.lower())

        # 2. Author filter
        if target_author:
            conditions.append(PenName.handle.ilike(target_author.lower()))

        # 3. Text query execution (PostgreSQL FTS vs SQLite)
        dialect_name = db.engine.dialect.name
        is_postgres = (dialect_name == "postgresql")

        if keywords:
            clean_kw = keywords[:100]  # Cap input length
            if is_postgres:
                tsvector = func.to_tsvector('english', Dispatch.title + ' ' + Dispatch.content_html)
                tsquery = func.websearch_to_tsquery('english', clean_kw)
                conditions.append(tsvector.op('@@')(tsquery))

                if sort_by == "relevance":
                    rank = func.ts_rank_cd(tsvector, tsquery)
                    stmt = stmt.order_by(rank.desc(), Dispatch.published_at.desc())
                else:
                    stmt = stmt.order_by(Dispatch.published_at.desc(), Dispatch.id.desc())
            else:
                kw_tokens = [t for t in re.split(r'\s+', clean_kw) if t]
                token_conditions = []
                for token in kw_tokens[:5]:
                    token_conditions.append(
                        or_(
                            Dispatch.title.ilike(f"%{token}%"),
                            Dispatch.content_html.ilike(f"%{token}%")
                        )
                    )
                if token_conditions:
                    conditions.append(and_(*token_conditions))

                if sort_by == "relevance":
                    stmt = stmt.order_by(
                        Dispatch.title.ilike(f"%{clean_kw}%").desc(),
                        Dispatch.published_at.desc()
                    )
                else:
                    stmt = stmt.order_by(Dispatch.published_at.desc(), Dispatch.id.desc())
        else:
            stmt = stmt.order_by(Dispatch.published_at.desc(), Dispatch.id.desc())

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Pagination with limit/offset
        safe_page = max(1, page)
        safe_page_size = min(50, max(5, page_size))
        offset = (safe_page - 1) * safe_page_size

        # Fetch page_size + 1 to detect if next page exists without full count query
        stmt = stmt.offset(offset).limit(safe_page_size + 1)
        results = db.session.execute(stmt).scalars().all()

        has_more = len(results) > safe_page_size
        items = results[:safe_page_size]

        # Attach highlighted excerpts to each dispatch
        for item in items:
            item.search_excerpt = cls.highlight_excerpt(item.content_html, keywords)

        result_data = {
            "dispatches": items,
            "has_more": has_more,
            "page": safe_page,
            "page_size": safe_page_size,
            "parsed": parsed,
            "keywords": keywords,
            "target_branch": target_branch,
            "target_author": target_author
        }

        # Cache top queries
        if len(cls._cache) >= cls._MAX_CACHE_SIZE:
            oldest_key = min(cls._cache.keys(), key=lambda k: cls._cache[k][0])
            del cls._cache[oldest_key]
        cls._cache[cache_key] = (now, result_data)

        return result_data

