import json
import sys


def main() -> int:
    event: str | None = None
    buf: list[str] = []

    def emit() -> None:
        nonlocal event, buf
        if event == "nested":
            try:
                obj = json.loads("\n".join(buf))
                stats = obj.get("stats") or {}
                sys.stdout.write(
                    "stats accounts={} locations={} reviews={}\n".format(
                        stats.get("accounts"),
                        stats.get("locations"),
                        stats.get("reviews"),
                    )
                )
                sys.stdout.flush()
            except Exception as exc:
                sys.stdout.write(f"parse_error {exc}\n")
                sys.stdout.flush()
        event = None
        buf = []

    for raw in sys.stdin:
        line = raw.rstrip("\n")
        if not line.strip():
            emit()
            continue
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            buf.append(line.split(":", 1)[1].lstrip())
            continue

    emit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
