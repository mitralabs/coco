import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, text
import logging

# Ensure a basic configuration is set here (or do this in the main entry before importing modules)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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


def get_vector_dim_from_db(session):
    """Get the vector dimension from the existing documents table"""
    # Check if the table exists
    inspector = inspect(engine)
    if "documents" not in inspector.get_table_names():
        return None

    try:
        result = session.execute(
            text(
                """
            SELECT atttypmod as dimension
            FROM pg_attribute
            WHERE attrelid = 'documents'::regclass
            AND attname = 'embedding';
        """
            )
        )
        dim = result.scalar()
        return dim
    except Exception as e:
        logging.error(f"Error getting vector dimension: {e}")
        return None


with SessionLocal() as session:
    session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    session.commit()

    table_emb_dim = get_vector_dim_from_db(session)
    if table_emb_dim is not None and table_emb_dim != EMBEDDING_DIM:
        logger.info(
            f"Dropping documents table: existing embedding dimension {table_emb_dim} != new {EMBEDDING_DIM}"
        )
        Base.metadata.drop_all(bind=engine, tables=[Document.__table__])
    Base.metadata.create_all(bind=engine)
    logger.info(f"Document embedding dimension: {get_vector_dim_from_db(session)}")


def get_db():
    """fastpi dependency to get db session

    Yields:
        _type_: _description_
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
