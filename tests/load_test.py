"""Load test: sequential concurrent requests against the local API."""
import concurrent.futures, requests, sys, time

BASE = "http://localhost:8000"
KEY = sys.argv[1] if len(sys.argv) > 1 else None
if not KEY:
    print("Usage: python load_test.py <sk-cust-...>")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
BODY = {"model": "mock-model", "messages": [{"role": "user", "content": "hello"}]}

def send(_):
    start = time.time()
    try:
        r = requests.post(f"{BASE}/v1/chat/completions", headers=HEADERS, json=BODY, timeout=30)
        return r.status_code, time.time() - start
    except Exception as e:
        return 0, time.time() - start

def main():
    for concurrency in (10, 25, 50):
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
            results = list(ex.map(send, range(concurrency)))
        codes = [c for c, _ in results]
        times = [t for _, t in results]
        ok = codes.count(200)
        r429 = codes.count(429)
        other = len(codes) - ok - r429
        avg = sum(times) / len(times)
        p95 = sorted(times)[int(len(times) * 0.95)]
        print(f"Concurrency {concurrency}: OK={ok} 429={r429} Other={other} avg={avg:.2f}s p95={p95:.2f}s")

if __name__ == "__main__":
    main()