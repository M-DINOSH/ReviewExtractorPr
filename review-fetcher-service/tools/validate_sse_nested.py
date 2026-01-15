import json
import sys


def _parse_int_flag(name: str, default: int) -> int:
    argv = sys.argv
    if name in argv:
        idx = argv.index(name)
        if idx + 1 >= len(argv):
            raise SystemExit(f"Missing value after {name}")
        return int(argv[idx + 1])
    return default


def main() -> int:
    min_locations = _parse_int_flag("--min-locations", 1)
    min_reviews = _parse_int_flag("--min-reviews", 1)

    event: str | None = None
    buf: list[str] = []

    last_printable: tuple[dict, dict, object] | None = None

    def emit() -> bool:
        nonlocal event, buf
        if event != "nested":
            event = None
            buf = []
            return False

        obj = json.loads("\n".join(buf))
        accounts = obj.get("accounts") or []
        total_locations = 0
        total_reviews = 0
        for account in accounts:
            locations = account.get("locations") or []
            total_locations += len(locations)
            for location in locations:
                reviews = location.get("reviews") or []
                total_reviews += len(reviews)

        stats = obj.get("stats") or {}
        computed = {
            "accounts": len(accounts),
            "locations": total_locations,
            "reviews": total_reviews,
        }

        mismatches: list[dict] = []
        for acc_block in accounts:
            acc = acc_block.get("account") or {}
            parent_acc_id = acc.get("account_id")
            try:
                parent_acc_int = int(str(parent_acc_id).split("/")[-1])
            except Exception:
                parent_acc_int = None
            for loc in acc_block.get("locations") or []:
                loc_acc_id = loc.get("google_account_id")
                try:
                    loc_acc_int = int(str(loc_acc_id).split("/")[-1])
                except Exception:
                    loc_acc_int = None
                if parent_acc_int is not None and loc_acc_int != parent_acc_int:
                    mismatches.append(
                        {
                            "parent_account_id": parent_acc_id,
                            "location_google_account_id": loc_acc_id,
                            "location_id": loc.get("location_id") or loc.get("id"),
                        }
                    )
                if len(mismatches) >= 5:
                    break
            if len(mismatches) >= 5:
                break

        nonlocal last_printable
        last_printable = (stats, computed, obj.get("joins_ok"))

        should_print = total_locations >= min_locations and total_reviews >= min_reviews

        event = None
        buf = []

        if should_print:
            print("nested_snapshot")
            print("stats", stats)
            print("computed", computed)
            print("joins_ok", obj.get("joins_ok"))
            if mismatches:
                print("account_location_mismatches", mismatches)
            return True

        return False

    for raw in sys.stdin:
        line = raw.rstrip("\n")
        if not line.strip():
            if emit():
                return 0
            continue
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            buf.append(line.split(":", 1)[1].lstrip())
            continue

    if last_printable is not None:
        stats, computed, joins_ok = last_printable
        print("nested_snapshot")
        print("stats", stats)
        print("computed", computed)
        print("joins_ok", joins_ok)
        return 0

    emit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
