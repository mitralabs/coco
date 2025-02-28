from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector
import os

# Get embedding dimension directly from environment
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    text = Column(String, nullable=False, unique=True)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    language = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    total_chunks = Column(Integer, nullable=False)
