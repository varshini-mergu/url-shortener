import asyncio
import httpx

CONCURRENCY = 10
API_KEY = "dev-key-12345"
BASE_URL = "http://localhost:3000"

async def make_request(client, code):
    try:
        # We do not follow redirects to directly check the 307 vs 500 status code
        resp = await client.get(f"{BASE_URL}/r/{code}", follow_redirects=False)
        return resp.status_code
    except Exception as e:
        return e

async def main():
    async with httpx.AsyncClient() as client:
        # 1. Dynamically create a shortened link
        print("[*] Creating a fresh shortened link...")
        try:
            create_resp = await client.post(
                f"{BASE_URL}/links/",
                headers={"X-API-Key": API_KEY},
                json={"long_url": "https://google.com"}
            )
            create_resp.raise_for_status()
            link_data = create_resp.json()
            code = link_data["code"]
            print(f"[+] Successfully created link. Short code: {code}")
        except Exception as e:
            print(f"[-] Failed to create shortened link: {e}")
            return

        # 2. Fire simultaneous concurrent GET requests
        print(f"[*] Firing {CONCURRENCY} concurrent redirect requests simultaneously...")
        tasks = [make_request(client, code) for _ in range(CONCURRENCY)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = [r for r in results if isinstance(r, int) and r in (301, 302, 307)]
    errors = [r for r in results if isinstance(r, int) and r == 500]
    exceptions = [r for r in results if isinstance(r, Exception) or not isinstance(r, int)]

    print("\n--- RESULTS ---")
    print(f"Successful Redirects (307): {len(successes)}")
    print(f"Server Errors (500): {len(errors)}")
    print(f"Exceptions/Network Errors: {len(exceptions)}")

    if errors:
        print("\n[!] BUG REPRODUCED: 500 errors occurred under concurrent load!")
    else:
        print("\n[+] No errors. Try running again or check your server logs.")

if __name__ == "__main__":
    asyncio.run(main())
