import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, text, Date


POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
VEKTOR_DIM = int(os.getenv("VEKTOR_DIM", "768"))
SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    text = Column(String, nullable=False, unique=True)
    embedding = Column(
        Vector(VEKTOR_DIM), nullable=False
    )  # dim for nomic model, change if necessary
    language = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    total_chunks = Column(Integer, nullable=False)

class DocumentWithDate(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    text = Column(String, nullable=False, unique=True)
    embedding = Column(
        Vector(VEKTOR_DIM), nullable=False
    )  # dim for nomic model, change if necessary
    language = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    total_chunks = Column(Integer, nullable=False)
    # turn into false at some point
    date = Column(Date, nullable=True)


with SessionLocal() as session:
    session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    session.commit()
    Base.metadata.create_all(bind=engine)


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
