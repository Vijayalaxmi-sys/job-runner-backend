import asyncio
import httpx


BASE_URL = "http://localhost:8000"

TENANT_ID = "11111111-1111-1111-1111-111111111111"


async def create_job(client):
    response = await client.post(
        f"{BASE_URL}/jobs",
        headers={
            "x-tenant-id": TENANT_ID,
            "idempotency-key": "race-test-001",
        },
        json={
            "type": "email",
            "payload": {
                "message": "Idempotency race test"
            },
            "estimated_cost": 10,
        },
    )

    return response.status_code, response.json()


def test_idempotency_concurrent_requests():

    async def run_test():

        async with httpx.AsyncClient() as client:

            tasks = [
                create_job(client)
                for _ in range(50)
            ]

            results = await asyncio.gather(*tasks)

        job_ids = set()

        for status, data in results:

            assert status in (200, 201)

            job_ids.add(data["id"])

        assert len(job_ids) == 1

    asyncio.run(run_test())