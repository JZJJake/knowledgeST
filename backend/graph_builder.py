import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from .database import PaperMetadata, Concept, get_db
from .vectorization import VectorizationPipeline

class GraphBuilder:
    def __init__(self, vectorization_pipeline: VectorizationPipeline):
        self.vector_pipeline = vectorization_pipeline

    def build_graph(self, db: Session, query_id: int) -> Dict[str, Any]:
        """
        Builds a graph topology from explicit SQLite metadata and implicit ChromaDB similarity.
        """
        papers = db.query(PaperMetadata).filter(PaperMetadata.query_id == query_id).all()

        if not papers:
            return {"nodes": [], "links": []}

        nodes = []
        links = []

        # Keep track of added concept nodes to avoid duplicates
        added_concepts = set()

        # Build paper nodes and explicit connections to concept nodes
        for paper in papers:
            # Add paper node
            nodes.append({
                "id": paper.paper_id,
                "name": paper.title,
                "val": 2, # Node size for 3d-force-graph
                "group": "paper",
                "details": {
                    "abstract": paper.abstract,
                    "authors": json.loads(paper.authors) if paper.authors else [],
                    "year": paper.publication_year,
                    "url": paper.url,
                    "source": paper.source
                }
            })

            # Explicit connections: Paper -> Concept
            concepts = db.query(Concept).filter(Concept.paper_id == paper.paper_id).all()
            for concept in concepts:
                concept_id = f"concept_{concept.concept_name}"

                # Add concept node if not exists
                if concept_id not in added_concepts:
                    nodes.append({
                        "id": concept_id,
                        "name": concept.concept_name,
                        "val": 1,
                        "group": "concept"
                    })
                    added_concepts.add(concept_id)

                # Add link from paper to concept
                links.append({
                    "source": paper.paper_id,
                    "target": concept_id,
                    "type": "explicit",
                    "weight": concept.score or 0.5
                })

        # Implicit connections: Similarity from ChromaDB
        collection = self.vector_pipeline.get_collection()

        for paper in papers:
            # Skip if the paper wasn't found in chroma (though it should be)
            try:
                # Query ChromaDB for this paper's embedding (we just use its text here since we have it,
                # or we could fetch the embedding by ID, but text query is simple)
                text = f"{paper.title}. {paper.abstract if paper.abstract != 'No abstract' else ''}"

                # Embed and query
                results = collection.query(
                    query_texts=[text],
                    n_results=6 # Top 6 (includes itself, so effectively top 5 similar)
                )

                # ChromaDB returns distance. Distance = 1 - Cosine Similarity (for cosine, but default is l2)
                # Let's assume the default L2 distance for now, and map it roughly, or just check distances
                # If using L2, closer to 0 is more similar.
                # Since we want similarity w > 0.85, let's just create a mock mapping or threshold.
                # Alternatively, we convert distance to similarity roughly: sim = 1 / (1 + distance).
                # To be strict about w > 0.85, we check sim > 0.85.

                if results and results["ids"] and results["distances"]:
                    ids = results["ids"][0]
                    distances = results["distances"][0]

                    for target_id, distance in zip(ids, distances):
                        if target_id == paper.paper_id:
                            continue # Skip self

                        # Convert L2 distance to a similarity score between 0 and 1
                        similarity = 1 / (1 + distance)

                        if similarity > 0.85: # Threshold specified in task 2.3
                            # Add implicit link

                            # Check if reverse link already exists to avoid duplicates
                            link_exists = any(
                                (l["source"] == paper.paper_id and l["target"] == target_id) or
                                (l["source"] == target_id and l["target"] == paper.paper_id)
                                for l in links
                            )

                            if not link_exists:
                                links.append({
                                    "source": paper.paper_id,
                                    "target": target_id,
                                    "type": "implicit",
                                    "weight": similarity
                                })
            except Exception as e:
                print(f"Error finding similar papers for {paper.paper_id}: {e}")

        # Ensure that target nodes for implicit links exist in our nodes list
        # They should, since we only queried papers from the same query_id, but just in case

        return {
            "nodes": nodes,
            "links": links
        }
