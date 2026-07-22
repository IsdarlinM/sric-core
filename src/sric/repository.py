from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class RecordRepository(Protocol):
    def health(self) -> dict[str, Any]: ...
    def put(self, record_id: str, kind: str, status: str, payload_json: str) -> None: ...
    def get(self, record_id: str) -> dict[str, Any] | None: ...


@dataclass
class SQLRecordRepository:
    """Storage adapter boundary for local SQLite and optional PostgreSQL collaboration.

    PostgreSQL is only activated with an explicit SQLAlchemy URL and installed driver. No remote
    database is contacted by default; local SQLite remains the secure default.
    """
    engine: Engine
    backend: str

    @classmethod
    def sqlite(cls, path: Path) -> "SQLRecordRepository":
        path.parent.mkdir(parents=True, exist_ok=True)
        repo=cls(create_engine(f"sqlite:///{path}",future=True),"sqlite")
        repo._bootstrap(); return repo

    @classmethod
    def from_url(cls, url: str) -> "SQLRecordRepository":
        if not url.startswith(("postgresql://","postgresql+psycopg://")):
            raise ValueError("collaboration database URL must use PostgreSQL")
        repo=cls(create_engine(url,future=True,pool_pre_ping=True),"postgresql")
        repo._bootstrap(); return repo

    def _bootstrap(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS sric_records (id VARCHAR(128) PRIMARY KEY, kind VARCHAR(64) NOT NULL, status VARCHAR(32) NOT NULL, payload_json TEXT NOT NULL)"))

    def health(self) -> dict[str, Any]:
        with self.engine.connect() as conn: value=conn.execute(text("SELECT 1")).scalar_one()
        return {"ok":value==1,"backend":self.backend}

    def put(self,record_id:str,kind:str,status:str,payload_json:str)->None:
        with self.engine.begin() as conn:
            if self.backend=="sqlite":
                conn.execute(text("INSERT INTO sric_records(id,kind,status,payload_json) VALUES(:id,:kind,:status,:payload) ON CONFLICT(id) DO UPDATE SET kind=:kind,status=:status,payload_json=:payload"),{"id":record_id,"kind":kind,"status":status,"payload":payload_json})
            else:
                conn.execute(text("INSERT INTO sric_records(id,kind,status,payload_json) VALUES(:id,:kind,:status,:payload) ON CONFLICT(id) DO UPDATE SET kind=EXCLUDED.kind,status=EXCLUDED.status,payload_json=EXCLUDED.payload_json"),{"id":record_id,"kind":kind,"status":status,"payload":payload_json})

    def get(self,record_id:str)->dict[str,Any]|None:
        with self.engine.connect() as conn: row=conn.execute(text("SELECT id,kind,status,payload_json FROM sric_records WHERE id=:id"),{"id":record_id}).mappings().first()
        return dict(row) if row else None
