"""Create documents table with pgvector support

Revision ID: d931e60d19f5
Revises: 
Create Date: 2025-02-28 18:40:47.273808

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
import logging
import os

# Import necessary modules for vector support
from pgvector.sqlalchemy import Vector

# Import utility functions for vector dimension checking
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from vector_utils import get_vector_dim_from_db, check_vector_dimensions, EMBEDDING_DIM

# revision identifiers, used by Alembic.
revision: str = "d931e60d19f5"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Setup logger
logger = logging.getLogger(__name__)

# A temporary Base class for table definition
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


def upgrade() -> None:
    # Create a connection to work with
    connection = op.get_bind()

    # Install pgvector extension if not already installed
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Check if documents table exists
    inspector = sa.inspect(connection)
    table_exists = "documents" in inspector.get_table_names()

    # If the table exists, check vector dimensions
    if table_exists:
        # Using the utility function to check vector dimensions
        need_recreate = check_vector_dimensions(connection, connection, "documents")
        if need_recreate:
            # Drop the existing table if dimensions don't match
            op.drop_table("documents")
            table_exists = False

    # Create the table if it doesn't exist or was dropped
    if not table_exists:
        # Create the documents table
        Document.__table__.create(connection)
        logger.info(
            f"Created documents table with embedding dimension: {EMBEDDING_DIM}"
        )


def downgrade() -> None:
    # Drop the documents table
    op.drop_table("documents")

    # Drop the pgvector extension
    op.execute("DROP EXTENSION IF EXISTS vector")
