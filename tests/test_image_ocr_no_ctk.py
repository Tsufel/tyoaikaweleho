"""image_ocr must import without customtkinter/tkinter (DLC API 2) and only
build the v1.3 preview dialog on demand."""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRIPT = r"""
import sys
sys.modules["customtkinter"] = None
sys.modules["tkinter"] = None
sys.modules["tkinter.messagebox"] = None
import image_ocr
assert image_ocr.DLC_API == 2, image_ocr.DLC_API
assert callable(image_ocr.extract_entries_from_image)
assert callable(image_ocr.save_confirmed_entries)
try:
    image_ocr.OcrPreviewDialog
except ImportError:
    pass
else:
    raise AssertionError("OcrPreviewDialog built without customtkinter")
try:
    image_ocr.no_such_thing
except AttributeError:
    pass
else:
    raise AssertionError("unknown attribute did not raise")
print("OK")
"""


def test_imports_without_gui_toolkit(tmp_path):
    pytest.importorskip("PIL")
    pytest.importorskip("winrt.windows.media.ocr")
    env = {**os.environ, "WELEHO_DATA_DIR": str(tmp_path)}
    out = subprocess.run([sys.executable, "-c", _SCRIPT], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "OK"


def test_preview_dialog_is_built_lazily():
    pytest.importorskip("customtkinter")
    pytest.importorskip("winrt.windows.media.ocr")
    import image_ocr
    cls = image_ocr.OcrPreviewDialog
    assert cls.__name__ == "OcrPreviewDialog"
    assert image_ocr.OcrPreviewDialog is cls
