import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OUTPUT = ROOT / "workers" / "funpay" / "railway" / "knowledge_repo.json"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def normalize_ws(text: str) -> str:
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def read_env_example(path: Path) -> str:
    if not path.exists():
        return ""
    lines = []
    for line in read_text(path).splitlines():
        line = line.rstrip()
        if not line:
            continue
        if line.startswith("#"):
            lines.append(line)
            continue
        # Keep KEY= lines, drop secrets
        if "=" in line:
            key, _ = line.split("=", 1)
            lines.append(f"{key}=")
    return "\n".join(lines)


def read_funpay_readme() -> str:
    path = ROOT / "workers" / "funpay" / "README.md"
    if not path.exists():
        return ""
    text = strip_html(read_text(path))
    return normalize_ws(text)


def read_commands_ru() -> str:
    path = ROOT / "workers" / "funpay" / "railway" / "constants.py"
    if not path.exists():
        return ""
    text = read_text(path)
    match = re.search(r"COMMANDS_RU\s*=\s*\((.*?)\)\n", text, re.DOTALL)
    if not match:
        return ""
    # Extract string literals inside the tuple.
    raw = match.group(1)
    parts = re.findall(r'"([^"]+)"|\'([^\']+)\'', raw)
    lines = []
    for a, b in parts:
        value = a or b
        if value:
            lines.append(value)
    return "\n".join(lines)


def build_items() -> list[dict]:
    items: list[dict] = []

    readme = read_funpay_readme()
    if readme:
        items.append(
            {
                "id": "funpay_readme",
                "keywords": [
                    "funpay",
                    "cardinal",
                    "бот",
                    "features",
                    "возможности",
                    "установка",
                    "install",
                ],
                "content": trim(readme, 1600),
            }
        )

    commands = read_commands_ru()
    if commands:
        items.append(
            {
                "id": "funpay_commands",
                "keywords": ["команды", "help", "commands", "бот", "funpay"],
                "content": commands,
            }
        )

    backend_env = read_env_example(ROOT / "apps" / "backend" / ".env.example")
    if backend_env:
        items.append(
            {
                "id": "backend_env",
                "keywords": ["env", "environment", "переменные", "backend", "mysql"],
                "content": "Backend .env variables:\n" + trim(backend_env, 1200),
            }
        )

    bridge_env = read_env_example(ROOT / "services" / "node-bridge" / ".env.example")
    if bridge_env:
        items.append(
            {
                "id": "node_bridge_env",
                "keywords": ["env", "environment", "steam", "bridge", "node"],
                "content": "Node bridge .env variables:\n" + trim(bridge_env, 800),
            }
        )

    return items


if __name__ == "__main__":
    items = build_items()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"items": items}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(items)} items")
