from sqlalchemy import inspect, text
import logging
import os

# Get embedding dimension directly from environment
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

logger = logging.getLogger(__name__)


def get_vector_dim_from_db(engine, session):
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


def check_vector_dimensions(engine, session, document_table):
    """Check and handle vector dimension changes

    Returns:
        bool: True if table needs to be recreated, False otherwise
    """
    table_emb_dim = get_vector_dim_from_db(engine, session)
    if table_emb_dim is not None and table_emb_dim != EMBEDDING_DIM:
        logger.info(
            f"Vector dimension mismatch: existing dimension {table_emb_dim} != new {EMBEDDING_DIM}"
        )
        return True
    return False
