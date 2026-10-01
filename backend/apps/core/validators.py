import re

from django.core.exceptions import ValidationError

# Same rule as the frontend (ui.js validateInput, data-type="phone").
NG_PHONE = re.compile(r"^(?:\+?234|0)([789][01]\d{8})$")


def normalize_ng_phone(value: str) -> str:
    """'+234 803 123 4567' / '08031234567' → '0803 123 4567'."""
    digits = re.sub(r"[\s\-()]", "", value or "")
    m = NG_PHONE.match(digits)
    if not m:
        raise ValidationError("Enter a valid Nigerian phone number (e.g. 0803 123 4567).")
    local = "0" + m.group(1)
    return f"{local[:4]} {local[4:7]} {local[7:]}"


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# Leading bytes of each allowed type — the extension alone proves nothing.
SIGNATURES = {
    "pdf": [b"%PDF-"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
}


def validate_document(upload):
    """WAEC/NECO result: PDF, JPG or PNG, at most 5 MB, contents must match the extension."""
    name = (upload.name or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in SIGNATURES:
        raise ValidationError("Upload a PDF, JPG or PNG file.")
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError("The file is larger than 5 MB.")
    head = upload.read(16)
    upload.seek(0)
    if not any(head.startswith(sig) for sig in SIGNATURES[ext]):
        raise ValidationError("This file doesn't look like a valid PDF, JPG or PNG.")
