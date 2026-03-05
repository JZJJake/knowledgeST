import chromadb
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from .database import PaperMetadata, SessionLocal

class VectorizationPipeline:
    def __init__(self, db_path: str = "./backend/chroma_db"):
        self.chroma_client = chromadb.PersistentClient(path=db_path)
        self.collection_name = "paper_abstracts"

        # We get or create the collection
        self.collection = self.chroma_client.get_or_create_collection(name=self.collection_name)

        # Load a local sentence transformer model for embeddings
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def vectorize_and_store(self, query_id: int):
        """
        Fetch papers for a given query, generate embeddings for their text (title + abstract),
        and store them in ChromaDB.
        """
        # Create a new DB session for this process
        db = SessionLocal()
        try:
            papers = db.query(PaperMetadata).filter(PaperMetadata.query_id == query_id).all()

            if not papers:
                print("No papers found to vectorize.")
                return

            documents = []
            metadatas = []
            ids = []

            for paper in papers:
                # Check if it's already in chroma to avoid re-embedding
                # In a real system, you'd probably check if it exists in chroma first
                # But for simplicity, we just overwrite/upsert

                # Combine title and abstract for embedding
                text = f"{paper.title}. {paper.abstract if paper.abstract != 'No abstract' else ''}"

                documents.append(text)
                metadatas.append({
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "year": paper.publication_year or 0,
                    "source": paper.source
                })
                ids.append(paper.paper_id)

            # Generate embeddings
            print(f"Generating embeddings for {len(documents)} papers...")
            embeddings = self.model.encode(documents).tolist()

            # Store in ChromaDB
            print("Upserting into ChromaDB...")
            self.collection.upsert(
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print("Vectorization complete.")
        finally:
            db.close()

    def get_collection(self):
        return self.collection
