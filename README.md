# ProofLayer

ProofLayer is a local-first PDF question answering and claim inspection app. It extracts text page by page, retrieves source passages, and returns grounded extractive answers when an LLM is not configured. Citations are IDs for returned passages and carry the page number read from the PDF.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- No Docker or external service credentials required for local use

## Start locally (PowerShell)

From the project root, in the first terminal:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python backend\migrate.py
uvicorn app.main:app --app-dir backend --reload
```

In a second terminal from the project root:

```powershell
npm install
npm run dev
```

Open <http://localhost:5173>. FastAPI documentation is at <http://localhost:8000/docs>; `/api/health` reports the active answer mode and whether an OpenAI credential is present.

The app reads optional overrides from `backend/.env`. Start from the safe template in `.env.example`:

```powershell
if (-not (Test-Path backend/.env)) { Copy-Item .env.example backend/.env }
```

The template contains no secret. Keep any real `OPENAI_API_KEY` in `backend/.env`; the current app reports its presence but does not send requests to an LLM. Local extractive answers work without credentials. Do not commit local `.env` files.

SQLite and uploaded PDFs are stored under the current working directory by default (`prooflayer.db` and `data/uploads`). Set `DATABASE_URL` and `STORAGE_DIR` in `backend/.env` to change those locations. SQLite is the tested local database. A PostgreSQL URL can be used when its driver is separately installed.

## Workflow

1. Upload a text-based PDF from Documents or Ask & Verify.
2. Select a source, ask a question, and inspect the returned source passages and claim statuses.
3. Open the Original PDF or switch to Extracted text. Page controls stay linked to the source page.
4. Export a JSON verification report from the answer or Reports.

Scanned PDFs are kept with an `unsupported_scanned` status and a clear explanation because OCR is not configured. The backend caps uploads at 20 MB.

## Storage and migrations

The SQLAlchemy models create missing tables on startup for convenient local development. Versioned SQL is also provided in `backend/migrations`. Apply it explicitly with `python backend/migrate.py`; migrations are idempotent. Existing rows and uploaded files are preserved.

## Deploy to Vercel

The repository includes a Vite build and a FastAPI Python Function entry point. Before deploying, connect a Postgres database and a **private** Vercel Blob store to the Vercel project. Vercel injects the database URL and Blob credentials into the project; the backend uses Postgres for document metadata and private Blob for PDF files. It reports `deployment_ready: false` until durable database and file storage are configured. Local development continues to use SQLite and `data/uploads`.

Vercel Functions accept smaller request bodies than the local API, so uploads are capped at 4 MB in production (20 MB locally). Scanned PDFs still need OCR, which is not configured. The app has no user login or per-user authorization: a public deployment is a shared workspace, and documents added there are visible to anyone who can access the API. Do not use it for confidential PDFs until authentication and document ownership are implemented.

The LLM integration is optional and unused by the current extractive answer path. No OpenAI credential is needed to deploy.

## Verification

From the project root:

```powershell
python -m pytest backend/tests -q -p no:cacheprovider
npm run lint
npm run build
```

Tests cover upload validation and PDF delivery, page extraction and citations, answerable and unanswerable questions, numeric conflicts, malformed requests, report export, and repeatable migrations.

## Verification limits

- Retrieval uses lexical overlap over sentence passages tied to their extracted PDF page. It is not a semantic search engine.
- Claim status uses deterministic overlap and numeric comparisons. It can miss paraphrases, negation, unit conversion, and context; it is a review aid, not a factual accuracy score.
- OCR is not available for image-only PDFs.
- The 3D object is an interface visualization; it does not represent document geometry or alter verification results.
- There is no authentication or multi-user authorization. Local development is intended for a trusted machine; a public deployment exposes a shared document library.
