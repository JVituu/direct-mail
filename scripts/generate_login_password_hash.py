from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT_TEXT = str(PROJECT_ROOT)
if PROJECT_ROOT_TEXT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_TEXT)

from app.shared.security.authenticator import password_hash


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Uso: python scripts/generate_login_password_hash.py "sua senha"')
        return 1

    print(password_hash(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
