"""Tiny standard-library writers for synthetic resumes (PDF and DOCX).

Only ASCII text is written, which keeps the PDF writer trivial.
"""

import io
import zipfile
from xml.sax.saxutils import escape


def _ascii(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


def make_pdf(lines: list[str]) -> bytes:
    """Single-font, multi-page PDF 1.4 with real text (extractable by pypdf)."""
    per_page = 46
    pages = [lines[i : i + per_page] for i in range(0, len(lines), per_page)] or [[""]]
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    add(b"<< /Type /Catalog /Pages 2 0 R >>")
    add(b"")  # placeholder for /Pages
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    for page_lines in pages:
        ops = ["BT", "/F1 11 Tf", "14 TL", "56 790 Td"]
        for i, line in enumerate(page_lines):
            safe = _ascii(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            size = "/F1 15 Tf" if i == 0 and page_lines is pages[0] else None
            if size:
                ops.append(size)
            ops.append(f"({safe}) Tj T*")
            if size:
                ops.append("/F1 11 Tf")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        content_id = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_ids.append(
            add(
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (font_id, content_id)
            )
        )
    kids = " ".join(f"{pid} 0 R" for pid in page_ids).encode()
    objects[1] = b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % len(page_ids)

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref))
    return out.getvalue()


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/></Relationships>'
)


def make_docx(lines: list[str]) -> bytes:
    paras = []
    for i, line in enumerate(lines):
        run_props = '<w:rPr><w:b/><w:sz w:val="30"/></w:rPr>' if i == 0 else ""
        paras.append(
            f'<w:p><w:r>{run_props}<w:t xml:space="preserve">{escape(_ascii(line))}</w:t></w:r></w:p>'
        )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>" + "".join(paras) + "</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("word/document.xml", document)
    return buf.getvalue()
