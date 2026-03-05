import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./backend/data.db"

# Ensure the directory exists
os.makedirs(os.path.dirname(DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    term = Column(String, unique=True, index=True)
    core_definition = Column(Text)
    search_terms = Column(Text) # Stored as JSON string
    time_span = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    papers = relationship("PaperMetadata", back_populates="query")

class PaperMetadata(Base):
    __tablename__ = "paper_metadata"

    id = Column(Integer, primary_key=True, index=True)
    query_id = Column(Integer, ForeignKey("query_history.id"))
    paper_id = Column(String, unique=True, index=True) # e.g., DOI or OpenAlex ID
    title = Column(String)
    abstract = Column(Text)
    authors = Column(Text) # JSON string
    publication_year = Column(Integer)
    source = Column(String) # CrossRef or OpenAlex
    url = Column(String)

    query = relationship("QueryHistory", back_populates="papers")
    concepts = relationship("Concept", back_populates="paper")

class Concept(Base):
    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(String, ForeignKey("paper_metadata.paper_id"))
    concept_name = Column(String, index=True)
    score = Column(Float) # Relevance score if provided

    paper = relationship("PaperMetadata", back_populates="concepts")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
