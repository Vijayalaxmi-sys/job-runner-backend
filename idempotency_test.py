import asyncio
import httpx

URL = "http://localhost:8000/jobs"

HEADERS = {
    "x-tenant-id": "11111111-1111-1111-1111-111111111111",
    "idempotency-key": "race-test-001",
}

BODY = {
    "type": "email",
    "payload": {
        "message": "Idempotency race test"
    },
    "estimated_cost": 10
}


async def send_job(client):
    response = await client.post(
        URL,
        headers=HEADERS,
        json=BODY,
    )

    return response.status_code, response.json()


async def main():
    async with httpx.AsyncClient() as client:

        tasks = [
            send_job(client)
            for _ in range(50)
        ]

        results = await asyncio.gather(*tasks)

    ids = set()

    for status, data in results:
        print(status, data["id"])
        ids.add(data["id"])

    print("\nUnique job IDs:", len(ids))


asyncio.run(main())