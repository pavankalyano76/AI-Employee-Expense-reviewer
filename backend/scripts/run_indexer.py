"""
Standalone policy indexer — run once to push all PDFs into Pinecone.

Usage (from backend/):
    source venv/bin/activate
    python -m scripts.run_indexer

The app lifespan skips indexing automatically when vectors are already present,
so running this script before starting the server is safe and idempotent.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))

from pinecone import Pinecone

from app.config import settings
from app.services.policy_indexer import index_policies

def main() -> None:
    print(f"Connecting to Pinecone index: {settings.pinecone_index_name!r}")
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(settings.pinecone_index_name)

    stats = index.describe_index_stats()
    existing = stats.total_vector_count
    print(f"Current vector count: {existing}")

    if existing > 0:
        print("Index already populated — nothing to do.")
        print("To re-index, delete all vectors in the Pinecone console first.")
        return

    print(f"Indexing policies from: {settings.policies_dir}\n")
    total = index_policies(index, settings.policies_dir)

    stats_after = index.describe_index_stats()
    print(f"\nDone. Vectors in Pinecone: {stats_after.total_vector_count} (indexed this run: {total})")


if __name__ == "__main__":
    main()
