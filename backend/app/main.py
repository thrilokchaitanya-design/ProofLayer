from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import fitz
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select, String, Text, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./prooflayer.db"
    storage_dir: str = "./data/uploads"
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 20
    openai_api_key: str = ""
    model_config = SettingsConfigDict(env_file="backend/.env", extra="ignore")

settings = Settings()
Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {})
Session = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase): pass
class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    page_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    error: Mapped[str] = mapped_column(Text, nullable=True)
    pages_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(String, index=True)
    question: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
Base.metadata.create_all(engine)

app = FastAPI(title="ProofLayer API", version="1.0.0", description="Evidence grounded document question answering and claim verification.")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])

def doc_out(d: Document):
    return {"id": d.id, "name": d.name, "page_count": d.page_count, "status": d.status, "error": d.error, "created_at": d.created_at.isoformat()}

def terms(text: str) -> set[str]:
    return {x.lower() for x in re.findall(r"[A-Za-z0-9]+", text) if len(x) > 2}

def retrieve(pages: list[dict], question: str, limit: int = 5):
    q = terms(question)
    ranked = []
    for page in pages:
        # Preserve page association; retrieve real extracted sentences with overlap.
        for i, sentence in enumerate(re.split(r"(?<=[.!?])\s+|\n+", page["text"])):
            sentence = sentence.strip()
            if len(sentence) < 15: continue
            overlap = len(q & terms(sentence))
            if overlap:
                ranked.append((overlap / max(1, len(q)), page, sentence, i))
    ranked.sort(key=lambda x: (x[0], len(x[2])), reverse=True)
    return [{"id": f"{p['number']}:{i}", "page": p["number"], "text": s, "score": round(score, 3)} for score, p, s, i in ranked[:limit]]

def numbers(s: str):
    return re.findall(r"(?<!\w)(?:[$\u20ac\u00a3]\s*|USD\s*)?\d[\d,]*(?:\.\d+)?\s*(?:%|percent|kg|km|miles?|years?|days?|USD|dollars?)?", s, flags=re.I)

def verify_claim(claim: str, evidence: list[dict]):
    cterms = terms(claim)
    scored = [(len(cterms & terms(e["text"])) / max(1, len(cterms)), e) for e in evidence]
    best = max(scored, default=(0, None), key=lambda x: x[0])
    contrad = []
    claim_nums = {re.sub(r"[\s,$\u20ac\u00a3]", "", n).lower() for n in numbers(claim)}
    for e in evidence:
        evidence_nums = {re.sub(r"[\s,$\u20ac\u00a3]", "", n).lower() for n in numbers(e["text"])}
        if claim_nums and evidence_nums and not claim_nums <= evidence_nums and len(cterms & terms(e["text"])) >= max(2, len(cterms)//3):
            contrad.append(e)
    if contrad:
        status, method, explanation = "contradicted", "deterministic_numeric_and_lexical", "A related source passage contains a different numeric value. Review units and context."
    elif best[0] >= .6:
        status, method, explanation = "supported", "lexical_overlap", "The cited passage shares key claim terms. This is a deterministic relevance check, not a semantic entailment guarantee."
    elif best[0] >= .3:
        status, method, explanation = "partially_supported", "lexical_overlap", "Some claim terms occur in the source, but the full claim is not established."
    else:
        status, method, explanation = "unverified", "insufficient_evidence", "No retrieved passage provides enough matching evidence to verify this claim."
    chosen = contrad if contrad else ([best[1]] if best[1] and status != "unverified" else [])
    return {"text": claim, "status": status, "evidence_ids": [e["id"] for e in chosen], "pages": sorted({e["page"] for e in chosen}), "method": method, "explanation": explanation, "warnings": ["Numeric comparison is string based; unit conversion is not performed."] if claim_nums else []}

class QuestionIn(BaseModel):
    document_id: str
    question: str = Field(min_length=3, max_length=2000)
class ClaimIn(BaseModel):
    text: str = Field(min_length=3, max_length=1000)
    document_id: str

@app.get("/api/health")
def health():
    return {"status": "ok", "llm_configured": bool(settings.openai_api_key), "answer_mode": "extractive", "database": "connected"}

@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)):
    if file.content_type != "application/pdf": raise HTTPException(415, "Upload a PDF file.")
    raw = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(raw) > settings.max_upload_mb * 1024 * 1024: raise HTTPException(413, f"PDF exceeds {settings.max_upload_mb} MB limit.")
    if not raw.startswith(b"%PDF-"): raise HTTPException(415, "File content is not a valid PDF.")
    try:
        pdf = fitz.open(stream=raw, filetype="pdf")
        pages = [{"number": i+1, "text": p.get_text("text").strip(), "blocks": [{"bbox": b[:4], "text": b[4]} for b in p.get_text("blocks") if len(b) > 4 and isinstance(b[4], str) and b[4].strip()]} for i, p in enumerate(pdf)]
        count = len(pdf); pdf.close()
    except Exception as exc: raise HTTPException(422, "PDF could not be read. It may be malformed or encrypted.") from exc
    if not count: raise HTTPException(422, "PDF contains no pages.")
    if not any(p["text"] for p in pages):
        status, error = "unsupported_scanned", "No selectable text found. Scanned PDFs require OCR, which is not configured."
    else: status, error = "ready", None
    ident = str(uuid.uuid4()); safe_name = Path(file.filename or "document.pdf").name[:255]
    Path(settings.storage_dir, ident + ".pdf").write_bytes(raw)
    with Session() as db:
        d = Document(id=ident, name=safe_name, page_count=count, status=status, error=error, pages_json=json.dumps(pages)); db.add(d); db.commit(); db.refresh(d)
        return doc_out(d)

@app.get("/api/documents")
def list_documents(q: str = ""):
    with Session() as db:
        docs = db.scalars(select(Document).order_by(Document.created_at.desc())).all()
        return [doc_out(d) for d in docs if q.lower() in d.name.lower()]

@app.get("/api/documents/{document_id}")
def get_document(document_id: str):
    with Session() as db:
        d = db.get(Document, document_id)
        if not d: raise HTTPException(404, "Document not found.")
        return {**doc_out(d), "pages": json.loads(d.pages_json)}

@app.get("/api/documents/{document_id}/file")
def get_document_file(document_id: str):
    with Session() as db:
        d = db.get(Document, document_id)
        if not d: raise HTTPException(404, "Document not found.")
        path = Path(settings.storage_dir, f"{d.id}.pdf")
        if not path.is_file(): raise HTTPException(404, "The stored PDF file is unavailable.")
        return FileResponse(
            path,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{d.id}.pdf"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

@app.get("/api/documents/{document_id}/pages/{page_number}")
def get_page(document_id: str, page_number: int):
    data = get_document(document_id); pages = data["pages"]
    if page_number < 1 or page_number > len(pages): raise HTTPException(404, "Page not found.")
    return pages[page_number-1]

@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str):
    with Session() as db:
        d = db.get(Document, document_id)
        if not d: raise HTTPException(404, "Document not found.")
        try: Path(settings.storage_dir, d.id + ".pdf").unlink(missing_ok=True)
        except OSError: pass
        db.query(Report).filter_by(document_id=document_id).delete(); db.delete(d); db.commit()
        return {"deleted": True}

@app.post("/api/questions")
def ask(payload: QuestionIn):
    data = get_document(payload.document_id)
    if data["status"] != "ready": raise HTTPException(422, data["error"] or "Document is not ready.")
    evidence = retrieve(data["pages"], payload.question)
    if not evidence:
        answer = "The document does not contain enough matching evidence to answer this question."
        claims = [{"text": answer, "status": "unverified", "evidence_ids": [], "pages": [], "method": "insufficient_evidence", "explanation": "No relevant passages were retrieved.", "warnings": []}]
    else:
        answer = " ".join(e["text"] for e in evidence[:3])
        claims = [verify_claim(s, evidence) for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
    assessed = max(1, sum(c["status"] != "unverified" for c in claims))
    citation_ok = sum(e["page"] in {p["number"] for p in data["pages"]} and bool(e["text"].strip()) for e in evidence)
    result = {"question": payload.question, "answer": answer, "claims": claims, "evidence": evidence, "metrics": {"claim_coverage": round(sum(c["status"] != "unverified" for c in claims)/max(1,len(claims)), 3), "citation_validity": round(citation_ok/len(evidence), 3) if evidence else 0.0, "evidence_support_rate": round(sum(c["status"] == "supported" for c in claims)/assessed, 3), "contradiction_rate": round(sum(c["status"] == "contradicted" for c in claims)/assessed, 3), "unverified_rate": round(sum(c["status"] == "unverified" for c in claims)/max(1,len(claims)), 3)}, "created_at": datetime.now(timezone.utc).isoformat(), "mode": "extractive"}
    with Session() as db:
        rid = str(uuid.uuid4()); db.add(Report(id=rid, document_id=payload.document_id, question=payload.question, result_json=json.dumps(result))); db.commit()
    return {"id": rid, "document_id": payload.document_id, **result}

@app.post("/api/claims/verify")
def check_claim(payload: ClaimIn):
    data = get_document(payload.document_id); evidence = retrieve(data["pages"], payload.text)
    return verify_claim(payload.text, evidence) | {"evidence": evidence}

@app.get("/api/reports")
def list_reports():
    with Session() as db:
        return [{"id": r.id, "document_id": r.document_id, "question": r.question, "created_at": r.created_at.isoformat()} for r in db.scalars(select(Report).order_by(Report.created_at.desc())).all()]
@app.get("/api/reports/{report_id}")
def get_report(report_id: str):
    with Session() as db:
        r = db.get(Report, report_id)
        if not r: raise HTTPException(404, "Report not found.")
        return {"id": r.id, "document_id": r.document_id, "created_at": r.created_at.isoformat(), **json.loads(r.result_json)}
@app.get("/api/reports/{report_id}/export")
def export_report(report_id: str):
    report = get_report(report_id)
    return Response(json.dumps(report, indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="prooflayer-{report_id}.json"'})
