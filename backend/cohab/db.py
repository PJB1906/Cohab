import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

# pool_pre_ping: Neon (and other serverless/autosuspending Postgres) closes
# idle connections when its compute suspends. Without this, the first
# request after any idle period reuses a dead pooled connection and 500s
# with "SSL connection has been closed unexpectedly" (found live, D-13.22) —
# pre_ping issues a lightweight check before handing a connection out and
# transparently replaces it if it's dead, instead of surfacing the error.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
