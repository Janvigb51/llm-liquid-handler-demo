"""Run a generated protocol through the Opentrons simulator (no robot needed)."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def simulate_protocol(source, timeout=120):
    """Return (status, output). status is 'ok', 'error' or 'unavailable'."""
    exe = shutil.which("opentrons_simulate")
    cmd_prefix = [exe] if exe else [sys.executable, "-m", "opentrons.simulate"]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "protocol.py"
        path.write_text(source)
        try:
            proc = subprocess.run(
                cmd_prefix + [str(path)], capture_output=True, text=True, timeout=timeout
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return "unavailable", str(exc)
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 and "No module named" in output and "opentrons" in output:
        return "unavailable", "opentrons is not installed (pip install opentrons)"
    return ("ok" if proc.returncode == 0 else "error"), output
