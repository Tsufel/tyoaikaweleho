"""WELEHO_DATA_DIR moves data.json, shifts.txt, error.log and session.json
into one directory and turns off the AppData migration."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRIPT = r"""
import json, storage, timer
print(json.dumps({"data_dir": storage.DATA_DIR, "data_file": storage.DATA_FILE,
                  "shifts": storage.SHIFTS_FILE, "log": storage.ERROR_LOG,
                  "appdata": storage._APPDATA_FILE, "session": timer._SESSION_FILE}))
"""


def test_override_redirects_everything(tmp_path):
    target = tmp_path / "weleho data"
    env = {**os.environ, "WELEHO_DATA_DIR": f"  {target}  "}
    out = subprocess.run([sys.executable, "-c", _SCRIPT], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    p = json.loads(out.stdout)
    d = os.path.abspath(str(target))
    assert p["data_dir"] == d and os.path.isdir(d)
    assert p["data_file"] == os.path.join(d, "data.json")
    assert p["shifts"] == os.path.join(d, "shifts.txt")
    assert p["log"] == os.path.join(d, "error.log")
    assert p["session"] == os.path.join(d, "session.json")
    assert p["appdata"] == ""
    assert os.listdir(d) == []      # importing must not create any data files


def test_fixtures_set_the_override(tmp_storage, tmp_timer):
    assert os.environ["WELEHO_DATA_DIR"] == str(tmp_storage)
