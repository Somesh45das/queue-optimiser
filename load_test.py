"""
Concurrent load test for Requirement 21.3 (>=100 concurrent users).

Runs a mix of read-only requests (login page, patient portal, crowd API,
CSV export) against a running server and reports throughput, latency
percentiles, and error rate. It does not need Locust or any external tool.

Usage:
    python load_test.py --url http://127.0.0.1:5000 --users 120 --duration 30
"""
import argparse
import statistics
import sys
import threading
import time
import urllib.request
from urllib.error import URLError

REQUESTS = [
    "/auth/login",
    "/patient/",
    "/patient/check-status",
    "/api/crowd-prediction?department_id=1",
    "/api/queue-stats",
    "/api/available-slots?doctor_id=1",
    "/api/doctors-by-department?department_id=1",
    "/api/crowd-timeline?department_id=1",
]


def worker(base_url, deadline, latencies, errors, stop_flag, index):
    session = urllib.request.build_opener()
    counter = index
    while time.perf_counter() < deadline and not stop_flag[0]:
        path = REQUESTS[counter % len(REQUESTS)]
        counter += 1
        start = time.perf_counter()
        try:
            with session.open(base_url + path, timeout=10) as resp:
                resp.read(4096)
                elapsed = (time.perf_counter() - start) * 1000
                if resp.status >= 500:
                    errors.append(f"{resp.status} {path}")
                else:
                    latencies.append(elapsed)
        except (URLError, TimeoutError, OSError) as exc:
            errors.append(f"{type(exc).__name__} {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--users", type=int, default=100,
                        help="Concurrent virtual users (default: 100)")
    parser.add_argument("--duration", type=int, default=30,
                        help="Test duration in seconds (default: 30)")
    args = parser.parse_args()

    latencies = []
    errors = []
    stop_flag = [False]
    deadline = time.perf_counter() + args.duration

    print(f"Firing {args.users} concurrent clients at {args.url} for {args.duration}s...\n")
    start_wall = time.perf_counter()

    threads = [
        threading.Thread(
            target=worker,
            args=(args.url, deadline, latencies, errors, stop_flag, i),
            daemon=True,
        )
        for i in range(args.users)
    ]
    for t in threads:
        t.start()

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        stop_flag[0] = True

    elapsed = time.perf_counter() - start_wall
    total = len(latencies) + len(errors)
    ok = len(latencies)

    if not total:
        print("No completed requests. Is the server running?")
        sys.exit(1)

    error_rate = len(errors) / total * 100
    throughput = ok / elapsed

    print("=" * 60)
    print(f"  Concurrent users : {args.users}")
    print(f"  Duration         : {elapsed:.1f} s")
    print(f"  Requests total   : {total:,}")
    print(f"  Successful       : {ok:,}")
    print(f"  Errors           : {len(errors):,} ({error_rate:.2f}%)")
    print(f"  Throughput       : {throughput:.1f} req/s")

    if latencies:
        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.99))]
        print(f"  Latency mean     : {statistics.mean(latencies):.1f} ms")
        print(f"  Latency p50/p95  : {p50:.1f} / {p95:.1f} ms")
        print(f"  Latency p99/max  : {p99:.1f} / {max(latencies):.1f} ms")

    print("=" * 60)
    # Requirement 21.4 approximation: <=0.5% errors during the run.
    success_rate = ok / total * 100
    verdict = "PASS" if error_rate <= 0.5 and args.users >= 100 else "REVIEW"
    print(f"  Success rate     : {success_rate:.2f}%   [{verdict}]")

    if errors:
        summary = {}
        for e in errors:
            summary[e] = summary.get(e, 0) + 1
        print("\n  Error breakdown:")
        for kind, count in sorted(summary.items(), key=lambda x: -x[1])[:5]:
            print(f"    {count:5d}  {kind}")


if __name__ == "__main__":
    main()
