import json
import time
import urllib.request
from urllib.parse import urlencode

BASE = "http://localhost:8084"


def post_json(path: str, payload: dict, timeout: int = 10) -> dict:
    url = BASE + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sse_next(resp, want_event: str, timeout: int = 30) -> dict:
    """Return the next SSE event payload (decoded JSON) for event name."""
    started = time.time()
    data_lines: list[str] = []
    cur_event: str | None = None

    while True:
        if time.time() - started > timeout:
            raise TimeoutError(f"timeout waiting for event={want_event}")

        line = resp.readline().decode("utf-8", errors="replace")
        if not line:
            time.sleep(0.05)
            continue

        line = line.rstrip("\n")

        if line.startswith("event:"):
            cur_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
        elif line == "":
            if cur_event == want_event and data_lines:
                payload = "\n".join(data_lines)
                return json.loads(payload)
            data_lines = []
            cur_event = None


def main() -> None:
    job = post_json("/api/v1/review-fetch", {"access_token": "test_token_123456789"}, timeout=10)
    job_id = job.get("job_id")
    print("job_id:", job_id)

    qs = urlencode({"job_id": job_id, "max_items": 200, "max_wait_sec": 60})

    acc_resp = urllib.request.urlopen(f"{BASE}/api/v1/demo/stream/accounts?{qs}", timeout=60)
    loc_resp = urllib.request.urlopen(f"{BASE}/api/v1/demo/stream/locations?{qs}", timeout=60)
    rev_resp = urllib.request.urlopen(f"{BASE}/api/v1/demo/stream/reviews?{qs}", timeout=60)

    try:
        account = sse_next(acc_resp, "account", timeout=40)
        wanted_account_id = int(account["account_id"])

        location = None
        for _ in range(800):
            loc = sse_next(loc_resp, "location", timeout=40)
            gaid = loc.get("google_account_id")
            if gaid is not None and int(gaid) == wanted_account_id:
                location = loc
                break
        if location is None:
            raise RuntimeError("No matching location found for streamed account")

        wanted_location_id = int(location["location_id"])

        review = None
        for _ in range(1500):
            r = sse_next(rev_resp, "review", timeout=40)
            if r.get("location_id") is not None and int(r["location_id"]) == wanted_location_id:
                review = r
                break
        if review is None:
            raise RuntimeError("No matching review found for streamed location")

        print("\nACCOUNT (schema)")
        print(json.dumps(account, indent=2))

        print("\nLOCATION (schema)")
        print(json.dumps(location, indent=2))

        print("\nREVIEW (schema)")
        print(json.dumps(review, indent=2))

        print("\nMATCH CHECKS")
        print(
            "account.account_id == location.google_account_id :",
            int(account["account_id"]) == int(location["google_account_id"]),
        )
        print(
            "location.location_id == review.location_id       :",
            int(location["location_id"]) == int(review["location_id"]),
        )

    finally:
        try:
            acc_resp.close()
        except Exception:
            pass
        try:
            loc_resp.close()
        except Exception:
            pass
        try:
            rev_resp.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
