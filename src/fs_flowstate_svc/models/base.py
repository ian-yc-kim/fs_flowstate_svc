from typing import Generator

from sqlalchemy import Column, PrimaryKeyConstraint, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from fs_flowstate_svc.config import settings

Base = declarative_base()

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
