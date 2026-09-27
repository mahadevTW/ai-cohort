"""Ticketing service: FastAPI REST API + a small web UI, backed by SQLite.

Run:  python ticketing-service/api_server.py        (http://localhost:8010)
Docs: http://localhost:8010/docs
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Field, Session, SQLModel, create_engine, func, or_, select

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("TICKETING_DB", BASE_DIR / "tickets.db"))
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


class Status(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TicketBase(SQLModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    priority: Priority = Priority.medium
    assignee: str | None = None


class Ticket(TicketBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    status: Status = Status.open
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class TicketCreate(TicketBase):
    pass


class TicketUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: Status | None = None
    priority: Priority | None = None
    assignee: str | None = None


def get_session():
    with Session(engine) as session:
        yield session


@asynccontextmanager
async def lifespan(_app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="ticketing-service", version="1.0.0", lifespan=lifespan)


@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/tickets", response_model=Ticket, status_code=201)
def create_ticket(payload: TicketCreate, session: Session = Depends(get_session)):
    ticket = Ticket.model_validate(payload)
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@app.get("/api/tickets", response_model=list[Ticket])
def list_tickets(
    status: Status | None = None,
    priority: Priority | None = None,
    assignee: str | None = None,
    q: str | None = Query(default=None, description="Search in title and description"),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    stmt = select(Ticket)
    if status:
        stmt = stmt.where(Ticket.status == status)
    if priority:
        stmt = stmt.where(Ticket.priority == priority)
    if assignee:
        stmt = stmt.where(Ticket.assignee == assignee)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Ticket.title.ilike(like), Ticket.description.ilike(like)))
    return session.exec(stmt.order_by(Ticket.updated_at.desc()).limit(limit)).all()


@app.get("/api/tickets/stats")
def ticket_stats(session: Session = Depends(get_session)):
    rows = session.exec(select(Ticket.status, func.count()).group_by(Ticket.status)).all()
    counts = {s.value: 0 for s in Status}
    counts.update({status.value: count for status, count in rows})
    return {"total": sum(counts.values()), "by_status": counts}


def _get_or_404(session: Session, ticket_id: int) -> Ticket:
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return ticket


@app.get("/api/tickets/{ticket_id}", response_model=Ticket)
def get_ticket(ticket_id: int, session: Session = Depends(get_session)):
    return _get_or_404(session, ticket_id)


@app.patch("/api/tickets/{ticket_id}", response_model=Ticket)
def update_ticket(ticket_id: int, payload: TicketUpdate, session: Session = Depends(get_session)):
    ticket = _get_or_404(session, ticket_id)
    ticket.sqlmodel_update(payload.model_dump(exclude_unset=True))
    ticket.updated_at = _now()
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@app.delete("/api/tickets/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: int, session: Session = Depends(get_session)):
    session.delete(_get_or_404(session, ticket_id))
    session.commit()


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=int(os.getenv("TICKETING_PORT", "8010")))
