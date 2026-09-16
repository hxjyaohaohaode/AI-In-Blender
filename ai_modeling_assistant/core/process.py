"""Non-blocking subprocess lifecycle. No Blender objects cross the boundary."""
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time


def python_executable():
    current = Path(sys.executable)
    if current.name.lower().startswith("python"):
        return str(current)
    for prefix in (Path(sys.prefix), Path(sys.base_prefix), current.parent):
        for pattern in ("bin/python.exe", "bin/python3", "bin/python3.*", "python.exe"):
            for candidate in sorted(prefix.glob(pattern)):
                if candidate.is_file() and not candidate.name.endswith((".dll", ".a")):
                    return str(candidate)
    raise RuntimeError("Cannot locate Blender's bundled Python executable")


class ProcessJob:
    def __init__(self, payload, *, executable=None):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(data) > 2_000_000:
            raise ValueError("Request context exceeds 2 MB; reduce scene/history detail")
        self.directory = tempfile.TemporaryDirectory(prefix="ai_in_blender_job_")
        self.output = open(Path(self.directory.name) / "result.json", "w+b")
        self.started = time.monotonic()
        self.timeout = float(payload["config"].get("timeout", 120)) + 5
        self.process = None
        self.closed = False
        worker = Path(__file__).resolve().parents[1] / "worker.py"
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            self.process = subprocess.Popen(
                [executable or python_executable(), str(worker)], stdin=subprocess.PIPE,
                stdout=self.output, stderr=subprocess.DEVNULL, env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.process.stdin.write(data)
            self.process.stdin.close()
        except Exception:
            self.cancel()
            raise

    def poll(self):
        if self.closed:
            return {"error": "Job was cancelled"}
        if self.process.poll() is None:
            if time.monotonic() - self.started <= self.timeout:
                return None
            self.cancel()
            return {"error": "Provider request timed out. Check remote job status before retrying."}
        try:
            self.output.seek(0)
            raw = self.output.read(16_000_001)
            if len(raw) > 16_000_000:
                raise ValueError("Worker result exceeds the size limit")
            if self.process.returncode:
                raise ValueError("Provider worker exited unexpectedly")
            result = json.loads(raw.decode("utf-8"))
            if not isinstance(result, dict):
                raise ValueError("Worker result is not an object")
            return result
        except (ValueError, UnicodeError):
            return {"error": "Provider worker returned an invalid result"}
        finally:
            self.close()

    def close(self):
        if not self.closed:
            self.output.close()
            self.directory.cleanup()
            self.closed = True

    def cancel(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=5)
        self.close()
