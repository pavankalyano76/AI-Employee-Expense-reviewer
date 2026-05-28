# Northwind Expense Reviewer

An AI-powered expense review system for Northwind Logistics. Finance reviewers upload employee travel receipts; the system extracts line items, checks each against the company policy library (stored in a vector database), and produces verdicts with exact policy citations. Managers can override any decision with a comment. Every action persists across restarts.

**Live demo:** [https://north-wind-expense-reviewer.vercel.app](https://north-wind-expense-reviewer.vercel.app)

**API (backend):** [https://north-wind-expense-reviewer-production.up.railway.app/docs](https://north-wind-expense-reviewer-production.up.railway.app/docs)

---

## Table of Contents

1. [Running Locally](#running-locally)
2. [Architecture](#architecture)
3. [Design Choices & Tradeoffs](#design-choices--tradeoffs)
4. [Cost Analysis & Scaling](#cost-analysis--scaling)
5. [What's Next](#whats-next)
6. [Evaluation Harness](#evaluation-harness)

---

## Running Locally

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| Pinecone account | free tier works |
| Anthropic API key | any Claude access tier |

### API Keys Required

| Key | Where to get it |
|-----|----------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `PINECONE_API_KEY` | [app.pinecone.io](https://app.pinecone.io) |
| `PINECONE_INDEX_NAME` | Create a Pinecone index: **384 dimensions, cosine metric** |

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in ANTHROPIC_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME

uvicorn app.main:app --reload --port 8000
```

On first startup the server:
1. Creates all SQLite tables
2. Seeds 5 employees and 6 submissions from `data/submissions/`
3. Indexes 8 policy PDFs into Pinecone (825 vectors) — **skip if already indexed**

### Frontend

```bash
cd frontend
npm install
# Optional: create .env.local and set VITE_API_URL=http://127.0.0.1:8000
npm run dev          # → http://localhost:5173
```

### Running the Evaluation Harness

```bash
cd backend
source venv/bin/activate
python ../eval/run_eval.py --cases ../eval/sample_cases.json --url http://localhost:8000
```

Drop in your own test file:

```bash
python ../eval/run_eval.py --cases /path/to/your_cases.json --url http://localhost:8000
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│   React + Vite · Tailwind CSS · React Router · Axios        │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/JSON
┌────────────────────────▼────────────────────────────────────┐
│                   FastAPI  (Python)                          │
│                                                             │
│  /employees   /submissions   /receipts   /verdicts          │
│  /overrides   /policy-qa                                    │
│                                                             │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ receipt_       │  │ verdict_     │  │ policy_qa      │  │
│  │ extractor      │  │ engine       │  │ service        │  │
│  │                │  │              │  │                │  │
│  │ PDF→pdfplumber │  │ embed query  │  │ embed query    │  │
│  │ Image→Claude   │  │ → Pinecone   │  │ → Pinecone     │  │
│  │ TXT→read_text  │  │ → Claude     │  │ → Claude       │  │
│  └────────────────┘  │   (tool use) │  │   (tool use)   │  │
│                      └──────────────┘  └────────────────┘  │
└──────┬───────────────────────┬─────────────────┬───────────┘
       │                       │                 │
┌──────▼──────┐   ┌────────────▼──────┐  ┌──────▼──────────┐
│   SQLite    │   │     Pinecone      │  │  Anthropic API  │
│             │   │                   │  │                 │
│ Employees   │   │ 825 vectors       │  │ claude-sonnet   │
│ Submissions │   │ 8 policy PDFs     │  │  verdicts + QA  │
│ Receipts    │   │ all-MiniLM-L6-v2  │  │ claude-haiku    │
│ Verdicts    │   │ (384-dim, cosine) │  │  image OCR      │
│ Overrides   │   └───────────────────┘  └─────────────────┘
└─────────────┘
```

### Data Flow — AI Review

```
Receipt uploaded
      │
      ▼
extract_receipt()
  ├─ .pdf  → pdfplumber → full text
  ├─ .jpg/.png/.webp → Claude Haiku Vision → structured JSON
  └─ .txt  → read_text()
      │
      ▼
verdict_engine.review_receipt()
  1. embed("{category} grade {N} employee expense") → all-MiniLM-L6-v2
  2. Pinecone top-6 (filter: category=travel_expense)
  3. Claude Sonnet (tool_choice=forced) → submit_verdict
     input:  receipt text + policy chunks
     output: {verdict, description, amount, reason, citations[], confidence}
      │
      ▼
LineItemVerdict stored in SQLite
      │
      ▼
Submission status = flagged | approved
(AI never emits "rejected" — that authority belongs to the manager)
```

---

## Design Choices & Tradeoffs

### Chunking Strategy — Hierarchical + Semantic

**What we do:** PDFs are split into numbered sections (regex on headings like `7.3 Hotel Limits`), then each section is split into sentences, then semantically merged using cosine similarity with a breakpoint at the 85th percentile.

**Why not fixed-token chunking:** Fixed chunks split mid-sentence and lose section context. A chunk that says "$250 per night" without its parent heading ("§7.3 Hotel Limits — Tier 1 Cities") is useless for citations.

**Tradeoff:** Semantic chunking is slower at index time and produces uneven chunk sizes. At 825 vectors for 8 PDFs this is fine; at 10,000 PDFs you'd pre-compute offline and cache embeddings.

**Why 85th percentile breakpoint:** Lower values over-split; higher values under-split and dilute relevance. 85% keeps sections intact while splitting genuinely distinct topics.

---

### Retrieval — Category-Filtered Pinecone

**What we do:** Each chunk is tagged with a `category` metadata field (`travel_expense`, `hr_policy`, etc.). Verdict queries filter to `travel_expense`; Policy Q&A queries span all categories.

**Why:** Without a category filter, a receipt for a hotel would surface chunks from the HR leave policy, contaminating the verdict reasoning. The filter halves irrelevant results and materially improves citation precision.

**Tradeoff:** The category taxonomy must be maintained. A new policy document must be tagged correctly at index time — a labelling error silently degrades retrieval. We accept this because the policy library is small and human-curated.

---

### Model Tier Selection

| Task | Model | Reason |
|------|-------|--------|
| Verdict reasoning | `claude-sonnet-4-6` | Requires multi-step policy reasoning and precise citation extraction |
| Policy Q&A | `claude-sonnet-4-6` | User-facing answers need nuance; citation accuracy matters |
| Image OCR | `claude-haiku-4-5` | Simple structured extraction; Haiku is ~10× cheaper than Sonnet for this task |

**Tradeoff on Haiku for OCR:** Haiku occasionally misreads stylised fonts or handwritten totals. We fall back to regex amount parsers when the model returns `null`, so a bad OCR doesn't silently zero out a line item — it surfaces as `needs_review`.

---

### When to Use a Vision Model

We use Claude Vision only for image receipts uploaded by the reviewer. We do **not** run it on PDFs (pdfplumber text extraction is faster, cheaper, and more reliable for machine-generated PDFs). The receipt extractor branches at file extension — image files get Vision, everything else gets text parsing.

---

### Flag vs Reject vs Ask a Human

**Policy:** The AI can only emit `approved`, `flagged`, or `needs_review`. It **cannot** emit `rejected`.

**Why:** Expense rejection has legal and HR consequences. A false positive that wrongly rejects a legitimate claim creates employee relations issues and potentially legal liability. The AI's role is to surface evidence and reasoning so a human manager can make an informed decision. Managers override through the UI; every override is logged with the manager's email, original status, new status, and written justification — a full audit trail.

**Confidence handling:** Claude returns a 0–1 confidence score via tool-use. We store it and display it as a progress bar. A low-confidence `approved` can be manually reviewed; a high-confidence `flagged` with precise citations gives the manager strong grounds to reject. We do not auto-reject on confidence alone.

---

### Persistence

SQLite for development. The schema is straightforward and all data persists across restarts. For production, the same SQLAlchemy models work against PostgreSQL with a one-line `DATABASE_URL` change. We intentionally avoided in-memory state anywhere in the API.

---

## Cost Analysis & Scaling

### Cost Per Submission (Estimates, May 2026 pricing)

| Step | Model | Tokens (avg) | Cost |
|------|-------|-------------|------|
| Receipt extraction × 6 PDFs | pdfplumber (local) | — | $0.000 |
| Receipt extraction × 1 image | claude-haiku-4-5 | ~600 in + 200 out | ~$0.001 |
| Verdict review × 6 receipts | claude-sonnet-4-6 | ~800 in + 150 out per receipt | ~$0.016 |
| Policy Q&A (optional, per query) | claude-sonnet-4-6 | ~1200 in + 200 out | ~$0.006 |
| Pinecone queries (top-6 × 6) | — | — | ~$0.001 |
| Embeddings (all-MiniLM, local) | — | — | $0.000 |
| **Total per submission (no Q&A)** | | | **~$0.02** |

### Scaling to 10,000 Submissions/Day

At 10k submissions/day that's ~$200/day in AI costs — manageable. The engineering changes needed:

| Layer | Change |
|-------|--------|
| Database | SQLite → PostgreSQL (connection pooling, concurrent writes) |
| AI review | Move to async Celery + Redis queue; review jobs run in background workers |
| Embeddings | Cache embedding model in worker process (already singleton); optionally use Pinecone's hosted inference |
| API | Horizontal scale FastAPI behind a load balancer (gunicorn + uvicorn workers) |
| Storage | S3 / GCS for uploaded receipt files instead of local filesystem |
| Cold start | Pre-warm worker pool; the SentenceTransformer model takes ~3s to load |

Cost at 10k/day: ~$200/day AI + ~$50/day infra = **~$250/day (~$7,500/month)**. Drops to ~$100/day if image receipts are < 20% of volume.

---

## What's Next

1. **Async review pipeline** — today review is synchronous (blocks the HTTP response). Move to a job queue so the UI shows a "reviewing…" state and polls for completion.
2. **PostgreSQL + Alembic migrations** — proper schema versioning for production.
3. **Authentication** — OAuth2/JWT; manager vs reviewer roles; scoped overrides.
4. **Multi-tenant** — isolate policy libraries and submission data per company.
5. **Policy version management** — when policy PDFs are updated, re-index only changed chunks; keep an audit trail of which policy version was active when each verdict was made.
6. **Batch re-review** — when a policy changes, automatically flag previously-approved submissions that may now be non-compliant.
7. **Mobile capture** — direct photo of a paper receipt → Vision extraction → instant upload.
8. **Analytics** — flagging rate by department, average spend by grade, most-cited policy clauses.
9. **Webhook notifications** — email manager when a submission is ready for review.
10. **Confidence threshold tuning** — collect manager override data over time; use it to calibrate when `needs_review` is genuinely useful vs noise.

---

## Evaluation Harness

See [`eval/run_eval.py`](eval/run_eval.py) for the full script.

### Quick Start

```bash
# against a local server
python eval/run_eval.py --cases eval/sample_cases.json --url http://localhost:8000

# against a deployed instance
python eval/run_eval.py --cases eval/sample_cases.json --url https://your-api.railway.app
```

### Dropping In Your Own Test File

The harness accepts a JSON file in this shape:

```json
{
  "version": "1.0",
  "test_cases": [
    {
      "id": "qa-001",
      "type": "policy_qa",
      "description": "In-scope meal limit question",
      "question": "What is the dinner limit for a grade 4 employee?",
      "expected": {
        "is_in_scope": true,
        "answer_mentions_any": ["$75", "$80", "75", "80"],
        "has_citations": true
      }
    },
    {
      "id": "qa-oos-001",
      "type": "policy_qa",
      "description": "Out-of-scope refusal",
      "question": "What is the capital of France?",
      "expected": {
        "is_in_scope": false
      }
    },
    {
      "id": "verdict-001",
      "type": "verdict",
      "description": "Economy flight — should be compliant",
      "receipt_content": "Alaska Airlines\nFlight AS-204 LAX→SEA\nEconomy Class\nTotal: $267.40\nDate: 2025-04-15",
      "receipt_filename": "eval_flight_economy.txt",
      "employee": {
        "employee_id": "EVAL-T01",
        "name": "Eval Tester",
        "grade": 4,
        "title": "Analyst",
        "department": "Evaluation"
      },
      "trip": {
        "trip_purpose": "Evaluation test trip",
        "trip_dates": "2025-04-15 to 2025-04-16"
      },
      "expected": {
        "verdict": "approved",
        "has_citations": true,
        "confidence_min": 0.6
      }
    }
  ]
}
```

### Metrics We Measure and Why

| Metric | What it measures | Why it matters |
|--------|-----------------|----------------|
| **Verdict accuracy** | % of AI verdicts matching expected (`approved`/`flagged`/`needs_review`) | Core correctness of the policy review engine |
| **Citation coverage** | % of responses with ≥ 1 citation when a citation is expected | Uncited verdicts are legally meaningless |
| **Citation correctness** | % of responses where citations contain expected doc/section references | Hallucinated citations are worse than no citations |
| **QA scope accuracy** | % of Q&A responses with correct `is_in_scope` classification | Prevents fabrication on non-policy questions |
| **QA answer quality** | % of in-scope answers containing expected keywords/values | Answer must be grounded in actual policy numbers |
| **Refusal rate on OOS** | % of out-of-scope questions correctly refused | System must not fabricate policy that doesn't exist |

The harness prints a results table and writes a timestamped JSON report to `eval/results_<timestamp>.json`.
