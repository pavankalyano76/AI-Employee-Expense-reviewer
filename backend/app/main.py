import logging
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pinecone import Pinecone
from sqlalchemy.orm import Session

from .api import employees as employees_router
from .api import overrides as overrides_router
from .api import policy_qa as policy_qa_router
from .api import receipts as receipts_router
from .api import submissions as submissions_router
from .api import verdicts as verdicts_router
from .config import settings
from .database import Base, SessionLocal, engine
from .models.db_models import Employee
from .services.policy_indexer import index_policies
from .services.seeder import seed_employees, seed_receipts, seed_submissions

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _seed_employees(db: Session) -> None:
    count = seed_employees(db, settings.submissions_dir)
    if count:
        logger.info("Seeded %d new employee(s)", count)
    else:
        logger.info("Employees already seeded — skipping")


def _index_policies(index) -> None:
    index_policies(index, settings.policies_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Ensure all tables exist
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")

    db: Session = SessionLocal()
    try:
        # 2. Seed employees if the table is empty
        employee_count = db.query(Employee).count()
        if employee_count == 0:
            logger.info("No employees found — seeding")
            _seed_employees(db)
        else:
            logger.info("Employees already present (%d) — skipping seed", employee_count)

        # 3. Seed submissions if the table is empty
        from .models.db_models import Submission as SubmissionModel
        submission_count = db.query(SubmissionModel).count()
        if submission_count == 0:
            logger.info("No submissions found — seeding")
            count = seed_submissions(db, settings.submissions_dir)
            logger.info("Seeded %d submission(s)", count)
        else:
            logger.info("Submissions already present (%d) — skipping seed", submission_count)

        # 4. Seed receipts if none exist yet
        from .models.db_models import Receipt as ReceiptModel
        receipt_count = db.query(ReceiptModel).count()
        if receipt_count == 0:
            logger.info("No receipts found — seeding")
            count = seed_receipts(db, settings.submissions_dir)
            logger.info("Seeded %d receipt(s)", count)
        else:
            logger.info("Receipts already present (%d) — skipping seed", receipt_count)

        # 5. Index policies if the Pinecone index is empty
        pc = Pinecone(api_key=settings.pinecone_api_key)
        index = pc.Index(settings.pinecone_index_name)
        stats = index.describe_index_stats()
        if stats.total_vector_count == 0:
            logger.info("Pinecone index empty — indexing policies")
            _index_policies(index)
        else:
            logger.info(
                "Policies already indexed (%d vectors) — skipping",
                stats.total_vector_count,
            )
    finally:
        db.close()

    # Store shared clients on app state — available to all request handlers
    app.state.pinecone_index = index
    app.state.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    logger.info("Pinecone and Anthropic clients ready")

    yield

    logger.info("Northwind shutdown complete")


app = FastAPI(
    title="Northwind Expense Reviewer API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employees_router.router, prefix="/employees", tags=["employees"])
app.include_router(submissions_router.router, prefix="/submissions", tags=["submissions"])
app.include_router(receipts_router.router, tags=["receipts"])
app.include_router(verdicts_router.router, tags=["verdicts"])
app.include_router(overrides_router.router, tags=["overrides"])
app.include_router(policy_qa_router.router, tags=["policy-qa"])


@app.get("/health")
async def health():
    return {"status": "ok"}
