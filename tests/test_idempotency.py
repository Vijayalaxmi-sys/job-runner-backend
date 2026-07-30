import httpx
import uuid


BASE_URL = "http://localhost:8000"

TENANT_ID = "11111111-1111-1111-1111-111111111111"


def test_idempotent_job_creation():

    headers = {
        "x-tenant-id": TENANT_ID,
        "idempotency-key": f"test-key-{uuid.uuid4()}",
    }

    payload = {
        "type": "email",
        "payload": {
            "message": "hello"
        },
        "estimated_cost": 50,
    }

    with httpx.Client() as client:

        first_response = client.post(
            f"{BASE_URL}/jobs",
            headers=headers,
            json=payload,
        )

        second_response = client.post(
            f"{BASE_URL}/jobs",
            headers=headers,
            json=payload,
        )

    assert first_response.status_code in (200, 201)
    assert second_response.status_code == 200

    first_job = first_response.json()
    second_job = second_response.json()

    assert first_job["id"] == second_job["id"]
    assert first_job["status"] == second_job["status"]