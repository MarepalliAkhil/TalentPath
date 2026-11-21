"""Resume validation and text extraction. Pure Python (pypdf + standard library),
no Django imports, so it is easy to test in isolation.

The file type is decided by the bytes, never by the file name or the
Content-Type header sent by the browser.
"""

import io
import re
import zipfile
from xml.etree import ElementTree

MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 200_000
MAX_PDF_PAGES = 30
MAX_DOCX_UNCOMPRESSED = 25 * 1024 * 1024
MAX_DOCX_ENTRIES = 2000

PDF = "pdf"
DOCX = "docx"
CONTENT_TYPES = {
    PDF: "application/pdf",
    DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ResumeError(ValueError):
    pass


def detect_type(data: bytes) -> str:
    if data[:5] == b"%PDF-":
        return PDF
    if data[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile as exc:
            raise ResumeError("The file looks damaged. Upload a PDF or DOCX.") from exc
        if "[Content_Types].xml" in names and "word/document.xml" in names:
            return DOCX
    raise ResumeError("Only PDF or DOCX resumes are accepted.")


def _clean(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_TEXT_CHARS]


def extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ResumeError("Password-protected PDFs are not supported.")
        pages = reader.pages[:MAX_PDF_PAGES]
        return _clean("\n".join(page.extract_text() or "" for page in pages))
    except ResumeError:
        raise
    except Exception as exc:  # pypdf raises many types on malformed input
        raise ResumeError("We could not read this PDF.") from exc


def extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_DOCX_ENTRIES:
                raise ResumeError("This DOCX has too many parts.")
            if sum(i.file_size for i in infos) > MAX_DOCX_UNCOMPRESSED:
                raise ResumeError("This DOCX expands to an unsafe size.")
            xml = zf.read("word/document.xml")
    except zipfile.BadZipFile as exc:
        raise ResumeError("The file looks damaged. Upload a PDF or DOCX.") from exc
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise ResumeError("This DOCX contains unsupported XML.")
    try:
        root = ElementTree.fromstring(xml)  # noqa: S314 - DOCTYPE/ENTITY rejected above
    except ElementTree.ParseError as exc:
        raise ResumeError("We could not read this DOCX.") from exc
    paragraphs = []
    for para in root.iter(f"{W_NS}p"):
        parts = []
        for node in para.iter():
            if node.tag == f"{W_NS}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{W_NS}tab":
                parts.append("\t")
            elif node.tag in (f"{W_NS}br", f"{W_NS}cr"):
                parts.append("\n")
        paragraphs.append("".join(parts))
    return _clean("\n".join(paragraphs))


def inspect_resume(data: bytes) -> tuple[str, str]:
    """Return (kind, text). Raises ResumeError with a user-facing message."""
    if not data:
        raise ResumeError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ResumeError("Resumes must be 5 MB or smaller.")
    kind = detect_type(data)
    text = extract_pdf(data) if kind == PDF else extract_docx(data)
    return kind, text


def safe_filename(name: str, kind: str) -> str:
    stem = (name or "resume").replace("\\", "/").rsplit("/", 1)[-1]
    stem = stem.rsplit(".", 1)[0] if "." in stem else stem
    stem = re.sub(r"[^A-Za-z0-9 _\-]+", "", stem).strip()[:80] or "resume"
    return f"{stem}.{kind}"
