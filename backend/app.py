from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .database import init_db, get_db, QueryHistory
from .deepseek_adapter import DeepSeekAdapter, TermExpansion
from .academic_fetcher import AcademicFetcher
from .vectorization import VectorizationPipeline
from .graph_builder import GraphBuilder

app = FastAPI(title="Academic Knowledge Graph API")

# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
init_db()

# Initialize modules
deepseek_adapter = DeepSeekAdapter()
vectorization_pipeline = VectorizationPipeline()
graph_builder = GraphBuilder(vectorization_pipeline)

class QueryRequest(BaseModel):
    term: str

@app.post("/api/query")
async def process_query(request: QueryRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Endpoint to trigger the full processing pipeline for a given term.
    """
    term = request.term

    # Check if term already exists
    existing_query = db.query(QueryHistory).filter(QueryHistory.term == term).first()

    if existing_query:
        # If it exists, return the ID immediately
        return {"status": "success", "message": "Query exists", "query_id": existing_query.id}

    try:
        # 1. Get semantic expansion from DeepSeek
        expansion = await deepseek_adapter.get_semantic_expansion(term)

        # 2. Fetch papers from CrossRef and OpenAlex and save to DB
        fetcher = AcademicFetcher(db)
        query_history = await fetcher.fetch_and_save(term, expansion)

        # 3. Vectorize and Store
        # To avoid a race condition where the frontend requests the graph before vectorization
        # is complete (missing implicit links), we'll do this synchronously for now.
        # In a production system, you'd use a background worker (Celery) and webhooks/polling.
        vectorization_pipeline.vectorize_and_store(query_history.id)

        return {
            "status": "success",
            "message": "Processing and vectorization complete",
            "query_id": query_history.id,
            "expansion": expansion.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/graph/{query_id}")
def get_graph(query_id: int, db: Session = Depends(get_db)):
    """
    Get the graph topology JSON for a given query ID.
    """
    # Check if query exists
    query = db.query(QueryHistory).filter(QueryHistory.id == query_id).first()
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    # Build graph
    graph_data = graph_builder.build_graph(db, query_id)

    if not graph_data["nodes"]:
        raise HTTPException(status_code=404, detail="No graph data available for this query")

    return graph_data
