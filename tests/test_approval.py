import asyncio
import httpx
import uuid


BASE_URL = "http://localhost:8000"

TENANT_ID = "11111111-1111-1111-1111-111111111111"


async def create_approval_job(client):

    response = await client.post(
        f"{BASE_URL}/jobs",
        headers={
            "x-tenant-id": TENANT_ID,
            "idempotency-key": f"approval-race-{uuid.uuid4()}",
        },
        json={
            "type": "email",
            "payload": {
                "message": "approval race test"
            },
            "estimated_cost": 200,
        },
    )

    return response.json()


async def approve_job(client, job_id):

    return await client.post(
        f"{BASE_URL}/jobs/{job_id}/approve",
        headers={
            "x-tenant-id": TENANT_ID,
        },
    )


async def reject_job(client, job_id):

    return await client.post(
        f"{BASE_URL}/jobs/{job_id}/reject",
        headers={
            "x-tenant-id": TENANT_ID,
        },
    )


def test_approval_race():

    async def run_test():

        async with httpx.AsyncClient() as client:

            job = await create_approval_job(client)

            print("CREATED JOB:", job)

            job_id = job["id"]

            tasks = []

            for _ in range(10):
                tasks.append(
                    approve_job(client, job_id)
                )

                tasks.append(
                    reject_job(client, job_id)
                )

            results = await asyncio.gather(
                *tasks
            )


        success_count = 0
        conflict_count = 0


        for response in results:

            print(
                "RESPONSE:",
                response.status_code,
                response.text
            )

            if response.status_code in (200, 201):
                success_count += 1

            elif response.status_code == 409:
                conflict_count += 1


        assert success_count == 1
        assert conflict_count == 19


    asyncio.run(run_test())