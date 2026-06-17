"""Release changelog — update this alongside version.py when cutting a release."""

CHANGELOG: dict[str, list[str]] = {
    "1.2.0": [
        "Overnight shift support: shifts spanning midnight now calculate correctly",
        "Time Out column shows '+1' indicator for overnight shifts",
        "Excel export: overnight shifts export correctly (=End-Start stays positive)",
        "Bare-hour time input: type '9' or '13' anywhere a time is entered",
        "Changelog popup: shows what's new on first launch after each update",
    ],
    "1.1.0": [
        "OCR engine switched to Windows built-in (winocr) — no Tesseract needed",
        "D.M. date format support for OCR import (e.g. 'Monday 4.5. 10-16')",
        "Remove Image OCR button added to Settings → DLC Store",
        "Image OCR DLC update notifications in Settings",
        "GitHub Actions updated to Node 24",
    ],
    "1.0.0": [
        "Initial release",
    ],
}
