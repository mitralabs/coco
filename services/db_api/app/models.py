from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector

from vector_utils import EMBEDDING_DIM

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    text = Column(String, nullable=False, unique=True)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    emotion_embedding = Column(Vector(EMBEDDING_DIM), nullable=True)
    language = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    session_id = Column(Integer, nullable=False)
    date_time = Column(DateTime, nullable=True)
