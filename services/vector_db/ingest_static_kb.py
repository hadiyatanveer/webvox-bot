"""
Static Knowledge Base Ingester for WebVox.
Loads PDF documents and other static files into the vector DB.

Usage:
    python3 -m services.vector_db.ingest_static_kb
"""

import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from utilities.config_loader import get_config
from services.vector_db.vector_store import get_vector_store
from services.vector_db.chunk_manager import get_chunk_manager
from services.vector_db.embedding_service import get_embedding_service
from services.vector_db.models import VectorChunk


def load_pdf_text(pdf_path: str) -> str:
    """
    Extract text from a PDF file.
    
    Tries multiple methods: PyPDF2, pdfplumber, or falls back to basic extraction.
    """
    text = ""
    
    # Try PyPDF2 first
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        if text.strip():
            return text
    except ImportError:
        print("  ⚠️ PyPDF2 not installed, trying pdfplumber...")
    except Exception as e:
        print(f"  ⚠️ PyPDF2 failed: {e}")
    
    # Try pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            return text
    except ImportError:
        print("  ⚠️ pdfplumber not installed")
    except Exception as e:
        print(f"  ⚠️ pdfplumber failed: {e}")
    
    # Fallback: return empty with warning
    print(f"  ❌ Could not extract text from {pdf_path}")
    print("     Install PyPDF2 or pdfplumber: pip install PyPDF2 pdfplumber")
    return ""


def load_text_file(file_path: str) -> str:
    """Load text from a plain text file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def ingest_document(
    file_path: str,
    entity_type: str = "static_kb",
    vector_store = None,
    chunk_manager = None
) -> int:
    """
    Ingest a single document into the static KB vector store.
    
    Returns:
        Number of chunks created
    """
    if vector_store is None:
        vector_store = get_vector_store()
    if chunk_manager is None:
        chunk_manager = get_chunk_manager()
    
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"  ❌ File not found: {file_path}")
        return 0
    
    # Extract text based on file type
    suffix = file_path.suffix.lower()
    
    if suffix == '.pdf':
        text = load_pdf_text(str(file_path))
    elif suffix in ['.txt', '.md', '.rst']:
        text = load_text_file(str(file_path))
    else:
        print(f"  ⚠️ Unsupported file type: {suffix}")
        return 0
    
    if not text.strip():
        print(f"  ⚠️ No text extracted from {file_path.name}")
        return 0
    
    # Create chunks with embeddings
    config = get_config()
    ttl_days = config.get('vector_db.ttl.static_kb_days', 30)
    
    chunks = chunk_manager.chunk_text(
        text=text,
        entity_type=entity_type,
        entity_id=file_path.stem,  # Use filename as entity ID
        source="static_kb",
        metadata={
            "filename": file_path.name,
            "file_path": str(file_path),
            "ingested_at": datetime.now().isoformat()
        }
    )
    
    # Override TTL for static KB
    for chunk in chunks:
        chunk.ttl_days = ttl_days
    
    if chunks:
        vector_store.add_chunks(chunks)
        print(f"  ✓ Created {len(chunks)} chunks from {file_path.name}")
    
    return len(chunks)


def ingest_static_kb(documents_path: Optional[str] = None) -> dict:
    """
    Ingest all static KB documents from the configured directory.
    
    Args:
        documents_path: Optional override for documents directory
        
    Returns:
        Statistics about ingestion
    """
    config = get_config()
    
    if documents_path is None:
        documents_path = config.get('static_kb.documents_path', 'data/static_kb/')
    
    # Get project root
    project_root = Path(__file__).parent.parent.parent
    docs_dir = project_root / documents_path
    
    print(f"\n📚 Static KB Ingestion")
    print(f"   Directory: {docs_dir}")
    
    if not docs_dir.exists():
        docs_dir.mkdir(parents=True, exist_ok=True)
        print(f"   Created directory: {docs_dir}")
    
    # Initialize services
    vector_store = get_vector_store()
    chunk_manager = get_chunk_manager()
    
    # Get files to process
    configured_files = config.get('static_kb.files', [])
    
    stats = {
        "files_processed": 0,
        "files_skipped": 0,
        "total_chunks": 0,
        "files": []
    }
    
    # Process configured files
    if configured_files:
        print(f"   Processing {len(configured_files)} configured files...")
        for filename in configured_files:
            file_path = docs_dir / filename
            if file_path.exists():
                chunks = ingest_document(
                    str(file_path), 
                    entity_type="menu" if "menu" in filename.lower() else "static_kb",
                    vector_store=vector_store,
                    chunk_manager=chunk_manager
                )
                stats["files_processed"] += 1
                stats["total_chunks"] += chunks
                stats["files"].append({"name": filename, "chunks": chunks})
            else:
                print(f"  ⚠️ Configured file not found: {filename}")
                stats["files_skipped"] += 1
    
    # Also process any other files in the directory
    for file_path in docs_dir.glob("*"):
        if file_path.is_file() and file_path.name not in configured_files:
            if file_path.suffix.lower() in ['.pdf', '.txt', '.md']:
                chunks = ingest_document(
                    str(file_path),
                    vector_store=vector_store,
                    chunk_manager=chunk_manager
                )
                stats["files_processed"] += 1
                stats["total_chunks"] += chunks
                stats["files"].append({"name": file_path.name, "chunks": chunks})
    
    # Print summary
    print(f"\n✅ Ingestion Complete")
    print(f"   Files processed: {stats['files_processed']}")
    print(f"   Total chunks: {stats['total_chunks']}")
    print(f"   Vector store stats: {vector_store.get_stats()}")
    
    return stats


def clear_static_kb():
    """Clear the static KB index."""
    vector_store = get_vector_store()
    vector_store.clear_index(source="static_kb")
    print("🗑️  Static KB index cleared")


if __name__ == "__main__":
    import sys
    
    print ("\n🚀 Starting Static KB Ingestion Script")
    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        clear_static_kb()
    else:
        ingest_static_kb()
