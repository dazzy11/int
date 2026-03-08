"""
resume_parser.py
Extracts text from uploaded PDF resumes using PyMuPDF (fitz).
Stores the extracted text in memory (a simple dict) keyed by session.
"""

import fitz  # PyMuPDF

# In-memory store: { session_id: resume_text }
resume_store = {}


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Open a PDF file and extract all text from every page.
    Returns the combined text as a single string.
    """
    doc = fitz.open(pdf_path)
    full_text = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        full_text.append(page.get_text())  # Extract plain text from page

    doc.close()
    return "\n".join(full_text).strip()


def save_resume(session_id: str, text: str):
    """
    Save extracted resume text to memory, keyed by session_id.
    """
    resume_store[session_id] = text


def get_resume(session_id: str) -> str:
    """
    Retrieve stored resume text for a session.
    Returns empty string if not found.
    """
    return resume_store.get(session_id, "")
