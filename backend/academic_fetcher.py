import aiohttp
import asyncio
import json
from typing import List, Dict, Any
from .database import get_db, PaperMetadata, QueryHistory, Concept
from .deepseek_adapter import TermExpansion
from sqlalchemy.orm import Session

class AcademicFetcher:
    def __init__(self, db: Session):
        self.db = db
        # Set OpenAlex rate limits and email as good practice
        self.headers = {"User-Agent": "mailto:academic-agent@example.com"}

    async def _fetch_openalex(self, session: aiohttp.ClientSession, query: str, time_span: str) -> List[Dict]:
        """Fetch papers from OpenAlex for a given query and timespan"""
        try:
            # Parse time_span assuming format YYYY-YYYY or simply start YYYY
            # Simple fallback parsing:
            parts = time_span.split('-')
            start_year = parts[0].strip() if len(parts) > 0 else "2000"
            end_year = parts[1].strip() if len(parts) > 1 else "2024"

            # Using basic searching on title/abstract in OpenAlex
            url = "https://api.openalex.org/works"
            params = {
                "search": query,
                "filter": f"publication_year:{start_year}-{end_year}",
                "per-page": 5 # Limit to 5 per search term for demonstration
            }

            async with session.get(url, params=params, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return [{"source": "OpenAlex", "data": item, "search_term": query} for item in data.get("results", [])]
                else:
                    print(f"OpenAlex Error for query {query}: {response.status}")
                    return []
        except Exception as e:
            print(f"Exception fetching from OpenAlex for query {query}: {e}")
            return []

    async def _fetch_crossref(self, session: aiohttp.ClientSession, query: str, time_span: str) -> List[Dict]:
        """Fetch papers from CrossRef for a given query and timespan"""
        try:
            # CrossRef API doesn't easily filter by a specific year range natively without complex filter strings,
            # so we will just query and limit results for demonstration.
            url = "https://api.crossref.org/works"
            params = {
                "query": query,
                "rows": 5
            }

            async with session.get(url, params=params, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get("message", {}).get("items", [])
                    return [{"source": "CrossRef", "data": item, "search_term": query} for item in items]
                else:
                    print(f"CrossRef Error for query {query}: {response.status}")
                    return []
        except Exception as e:
            print(f"Exception fetching from CrossRef for query {query}: {e}")
            return []

    def _parse_openalex_item(self, item: Dict) -> Dict[str, Any]:
        data = item["data"]
        authors = [a.get("author", {}).get("display_name") for a in data.get("authorships", [])]
        concepts = [{"name": c.get("display_name"), "score": c.get("score")} for c in data.get("concepts", [])]

        return {
            "paper_id": f"openalex_{data.get('id', '')}",
            "title": data.get("title", "Unknown Title"),
            "abstract": data.get("abstract_inverted_index", "No abstract"), # We would normally decode this inverted index
            "authors": json.dumps(authors),
            "publication_year": data.get("publication_year"),
            "source": "OpenAlex",
            "url": data.get("doi") or data.get("id"),
            "concepts": concepts
        }

    def _parse_crossref_item(self, item: Dict) -> Dict[str, Any]:
        data = item["data"]
        authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in data.get("author", [])]

        # Simple extraction of subject/concepts if available
        concepts = [{"name": s, "score": 1.0} for s in data.get("subject", [])[:5]]

        # Crossref dates can be messy, grab the year
        pub_year = None
        created = data.get("created", {}).get("date-parts")
        if created and len(created) > 0 and len(created[0]) > 0:
            pub_year = created[0][0]

        return {
            "paper_id": f"crossref_{data.get('DOI', '')}",
            "title": data.get("title", ["Unknown Title"])[0] if data.get("title") else "Unknown Title",
            "abstract": data.get("abstract", "No abstract"),
            "authors": json.dumps(authors),
            "publication_year": pub_year,
            "source": "CrossRef",
            "url": data.get("URL") or data.get("DOI"),
            "concepts": concepts
        }

    async def fetch_and_save(self, term: str, expansion: TermExpansion) -> QueryHistory:
        """Create batch asynchronous request queue, fetch, parse, and save to SQLite"""

        # 1. Save Query History
        query_history = self.db.query(QueryHistory).filter(QueryHistory.term == term).first()
        if not query_history:
            query_history = QueryHistory(
                term=term,
                core_definition=expansion.core_definition,
                search_terms=json.dumps(expansion.search_terms),
                time_span=expansion.time_span
            )
            self.db.add(query_history)
            self.db.commit()
            self.db.refresh(query_history)

        # 2. Build Async Queue for Fetching
        tasks = []
        async with aiohttp.ClientSession() as session:
            for search_term in expansion.search_terms:
                tasks.append(self._fetch_openalex(session, search_term, expansion.time_span))
                tasks.append(self._fetch_crossref(session, search_term, expansion.time_span))

            # Execute batch requests concurrently
            results = await asyncio.gather(*tasks)

        # 3. Flatten results
        all_raw_papers = []
        for r in results:
            all_raw_papers.extend(r)

        # 4. Parse and Save to Local DB (Download immediately written to disk)
        parsed_papers = []

        for item in all_raw_papers:
            if item["source"] == "OpenAlex":
                parsed = self._parse_openalex_item(item)
            else:
                parsed = self._parse_crossref_item(item)

            # Basic deduplication by paper_id
            existing = self.db.query(PaperMetadata).filter(PaperMetadata.paper_id == parsed["paper_id"]).first()
            if not existing:
                paper = PaperMetadata(
                    query_id=query_history.id,
                    paper_id=parsed["paper_id"],
                    title=parsed["title"][:255], # Limit length
                    abstract=str(parsed["abstract"]), # Converting to str (OpenAlex inverted index is complex but we'll store str rep)
                    authors=parsed["authors"],
                    publication_year=parsed["publication_year"],
                    source=parsed["source"],
                    url=parsed["url"]
                )
                self.db.add(paper)
                self.db.flush() # Flush to get paper.paper_id associated

                # Save concepts
                for concept_data in parsed["concepts"]:
                    if concept_data["name"]:
                        concept = Concept(
                            paper_id=paper.paper_id,
                            concept_name=concept_data["name"][:100],
                            score=concept_data["score"]
                        )
                        self.db.add(concept)

                parsed_papers.append(paper)

        self.db.commit()
        return query_history
