import asyncio
import pytest

from app.worker import claim_one_job
from app.db import get_pool


@pytest.mark.asyncio
async def test_only_one_worker_claims_each_job():

    pool = get_pool()

    await pool.open(
        wait=True,
        timeout=30,
    )

    worker_ids = [
        "worker-1",
        "worker-2",
        "worker-3",
        "worker-4",
    ]

    claimed_jobs = []

    async def claim(worker_id):

        job = await claim_one_job(worker_id)

        if job:
            claimed_jobs.append(
                (
                    str(job["id"]),
                    worker_id,
                )
            )

    await asyncio.gather(
        *(claim(worker_id) for worker_id in worker_ids)
    )

    job_ids = [
        job_id
        for job_id, worker_id in claimed_jobs
    ]

    # Verify no job was claimed by multiple workers
    assert len(job_ids) == len(set(job_ids))

    # IMPORTANT:
    # Do NOT close the global pool here.
    # Other tests use the same pool.