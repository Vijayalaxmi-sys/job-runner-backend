import time
import psycopg
import httpx


BASE_URL = "http://localhost:8000"

TENANT_ID = "11111111-1111-1111-1111-111111111111"

DATABASE_URL = (
    "postgresql://app:app@db:5432/app"
)


def test_exactly_one_side_effect():

    headers = {
        "x-tenant-id": TENANT_ID,
        "idempotency-key": "side-effect-test-001",
    }

    payload = {
        "type": "email",
        "payload": {
            "message": "side effect validation"
        },
        "estimated_cost": 10,
    }

    with httpx.Client() as client:

        response = client.post(
            f"{BASE_URL}/jobs",
            headers=headers,
            json=payload,
        )

    assert response.status_code in (200, 201)

    job_id = response.json()["id"]

    completed = False

    for _ in range(30):

        time.sleep(1)

        with httpx.Client() as client:

            job_response = client.get(
                f"{BASE_URL}/jobs/{job_id}",
                headers={
                    "x-tenant-id": TENANT_ID,
                },
            )

        job = job_response.json()

        if job["status"] == "succeeded":
            completed = True
            break

    assert completed is True

    with psycopg.connect(DATABASE_URL) as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM side_effects
                WHERE job_id = %s
                """,
                (job_id,),
            )

            count = cursor.fetchone()[0]

    assert count == 1