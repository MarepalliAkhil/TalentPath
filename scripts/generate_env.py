"""Create backend/.env from backend/.env.example with fresh random secrets.

    python scripts/generate_env.py

Standard library only. Refuses to overwrite an existing .env.
"""

import base64
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "backend" / ".env.example"
TARGET = ROOT / "backend" / ".env"


def key32() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


GENERATED = {
    "SECRET_KEY": lambda: secrets.token_urlsafe(50),
    "FIELD_ENCRYPTION_KEY": key32,
    "BLIND_INDEX_KEY": key32,
    "INTERNAL_TICK_SECRET": lambda: secrets.token_urlsafe(32),
}


def main() -> int:
    if TARGET.exists():
        print(f"{TARGET} already exists; leaving it untouched.")
        return 0
    lines = []
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() in GENERATED and not value.strip():
            line = f"{key.strip()}={GENERATED[key.strip()]()}"
        lines.append(line)
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {TARGET} with fresh secrets. Keep it out of git (it is in .gitignore).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
