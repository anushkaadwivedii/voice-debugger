"""Start the local browser server and, when configured, the agent worker."""

import subprocess
import sys
import time

from .config import ROOT, load_settings


def main():
    if not (ROOT / "dist/index.html").is_file():
        raise SystemExit("Run npm run build before starting Voice Debugger.")
    children = []
    try:
        children.append(subprocess.Popen([sys.executable, "-m", "voice_debugger.server"], cwd=ROOT))
        settings = load_settings()
        if settings.missing:
            print("\nAdd your account credentials to .env, then restart this command.", flush=True)
        else:
            children.append(subprocess.Popen([sys.executable, "-m", "voice_debugger.agent", "dev"], cwd=ROOT))
        print("\nVoice Debugger: http://127.0.0.1:8000\nPress Control-C to stop.\n", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        raise SystemExit("A component stopped. Review its message above, then restart.")
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
