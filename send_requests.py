import urllib.request
import json
from concurrent.futures import ThreadPoolExecutor

def hit_ready():
    try:
        with urllib.request.urlopen("http://localhost:3000/ready") as resp:
            resp.read()
    except Exception:
        pass

def main():
    print("Sending 500 requests to /ready...")
    with ThreadPoolExecutor(max_workers=50) as executor:
        list(executor.map(lambda _: hit_ready(), range(500)))
    
    print("Done. Fetching memory stats...")
    try:
        with urllib.request.urlopen("http://localhost:3000/debug/memory") as resp:
            stats = json.loads(resp.read().decode())
            print("Top allocations:")
            for alloc in stats["top_allocations"][:5]:
                print(alloc)
    except Exception as e:
        print("Error fetching stats:", e)

if __name__ == "__main__":
    main()
