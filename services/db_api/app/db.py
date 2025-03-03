import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_url import SQLALCHEMY_DATABASE_URL
from models import Document
from vector_utils import get_vector_dim_from_db

# Get embedding dimension directly from environment
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

# Ensure a basic configuration is set here (or do this in the main entry before importing modules)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create engine and session factory
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Log the actual embedding dimension from the database
try:
    # Create a temporary session to check the vector dimension
    temp_session = SessionLocal()
    db_embedding_dim = get_vector_dim_from_db(engine, temp_session)
    if db_embedding_dim is not None:
        logger.info(f"Database vector embedding dimension: {db_embedding_dim}")
    else:
        logger.info(f"Using configured embedding dimension: {EMBEDDING_DIM}")
    temp_session.close()
except Exception as e:
    logger.error(f"Could not check database embedding dimension: {e}")
    logger.info(f"Using configured embedding dimension: {EMBEDDING_DIM}")


def get_db():
    """FastAPI dependency to get db session

    Yields:
        Session: A SQLAlchemy session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
