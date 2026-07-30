import pytest

from app.worker import claim_one_job
from app.db import get_pool


@pytest.mark.asyncio
async def test_worker_recovers_expired_lease():

    pool = get_pool()

    await pool.open(
        wait=True,
        timeout=30,
    )

    job_id = None

    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cursor:

                await cursor.execute(
                    """
                    INSERT INTO jobs (
                        id,
                        tenant_id,
                        idempotency_key,
                        type,
                        payload,
                        estimated_cost,
                        status,
                        attempts,
                        max_attempts,
                        leased_by,
                        lease_until
                    )
                    VALUES (
                        gen_random_uuid(),
                        '11111111-1111-1111-1111-111111111111',
                        'worker-recovery-' || gen_random_uuid()::text,
                        'email',
                        '{"message":"recovery test"}',
                        10,
                        'running',
                        1,
                        3,
                        'dead-worker',
                        now() - interval '10 seconds'
                    )
                    RETURNING id
                    """
                )

                row = await cursor.fetchone()
                job_id = row[0]


    recovered_job = await claim_one_job(
        "replacement-worker"
    )

    assert recovered_job is not None
    assert str(recovered_job["id"]) == str(job_id)
    assert recovered_job["leased_by"] == "replacement-worker"

    # Do not close global pool