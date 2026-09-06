from __future__ import annotations

from app.db.base import Base
from app.db.session import engine

# Import models so SQLAlchemy registers tables.
import app.db.models  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("database tables created")

