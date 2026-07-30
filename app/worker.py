"""Worker entrypoint. Runs as its own process — and several run at once.

Right now it idles. Everything past the TODO is yours.
"""

from __future__ import annotations

import asyncio
import logging
import os
from uuid import uuid4

from psycopg.rows import dict_row

from app.db import get_pool
from app.executor import TransientExecutionError, execute

LEASE_SECONDS = int(os.getenv("JOB_LEASE_SECONDS", "30"))
POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "0.5"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
log = logging.getLogger("worker")


async def claim_one_job(worker_id: str):
    """Atomically claim one queued job or reclaim an expired job."""

    pool = get_pool()

    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor(row_factory=dict_row) as cursor:

                await cursor.execute(
                    """
                    UPDATE jobs
                    SET status = 'failed',
                        leased_by = NULL,
                        lease_until = NULL,
                        updated_at = now()
                    WHERE status = 'running'
                      AND lease_until < now()
                      AND attempts >= max_attempts
                    """
                )

                await cursor.execute(
                    """
                    SELECT id
                    FROM jobs
                    WHERE (
                        status = 'queued'
                        OR (
                            status = 'running'
                            AND lease_until < now()
                        )
                    )
                    AND attempts < max_attempts
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                )

                available_job = await cursor.fetchone()

                if available_job is None:
                    return None

                await cursor.execute(
                    """
                    UPDATE jobs
                    SET status = 'running',
                        attempts = attempts + 1,
                        leased_by = %s,
                        lease_until =
                            now() + (%s * interval '1 second'),
                        updated_at = now()
                    WHERE id = %s
                    RETURNING
                        id,
                        type,
                        payload,
                        attempts,
                        max_attempts,
                        leased_by,
                        lease_until
                    """,
                    (
                        worker_id,
                        LEASE_SECONDS,
                        available_job["id"],
                    ),
                )

                return await cursor.fetchone()


async def record_failure(worker_id: str, job: dict) -> None:
    """Retry the job or mark it permanently failed."""

    if job["attempts"] < job["max_attempts"]:
        next_status = "queued"
    else:
        next_status = "failed"

    pool = get_pool()

    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE jobs
                    SET status = %s,
                        leased_by = NULL,
                        lease_until = NULL,
                        updated_at = now()
                    WHERE id = %s
                      AND status = 'running'
                      AND leased_by = %s
                    """,
                    (
                        next_status,
                        job["id"],
                        worker_id,
                    ),
                )

    log.info(
        "job %s moved to %s",
        job["id"],
        next_status,
    )


async def run_job(worker_id: str, job: dict) -> None:
    """Run the executor and record the result transactionally."""

    pool = get_pool()

    try:
        async with pool.connection() as conn:
            async with conn.transaction():

                try:
                    result = await execute(
                        conn,
                        job["id"],
                        job["type"],
                        job["payload"],
                    )

                except Exception as exc:

                    # Recover if provider side effect already happened
                    # but worker crashed before job completion update.
                    async with conn.cursor(
                        row_factory=dict_row
                    ) as cursor:

                        await cursor.execute(
                            """
                            SELECT payload
                            FROM side_effects
                            WHERE job_id = %s
                            """,
                            (
                                str(job["id"]),
                            ),
                        )

                        existing_effect = await cursor.fetchone()

                    if existing_effect is not None:
                        result = existing_effect["payload"]
                    else:
                        raise exc


                async with conn.cursor(
                    row_factory=dict_row
                ) as cursor:

                    await cursor.execute(
                        """
                        UPDATE jobs
                        SET status = 'succeeded',
                            leased_by = NULL,
                            lease_until = NULL,
                            updated_at = now()
                        WHERE id = %s
                          AND status = 'running'
                          AND leased_by = %s
                        RETURNING id, status
                        """,
                        (
                            job["id"],
                            worker_id,
                        ),
                    )

                    completed_job = await cursor.fetchone()

                    if completed_job is None:
                        raise RuntimeError(
                            f"worker no longer owns job {job['id']}"
                        )

                log.info(
                    "job succeeded id=%s result=%s",
                    job["id"],
                    result,
                )


    except TransientExecutionError as exc:

        log.warning(
            "job failed id=%s attempt=%s/%s error=%s",
            job["id"],
            job["attempts"],
            job["max_attempts"],
            exc,
        )

        await record_failure(worker_id, job)


    except Exception:

        log.exception(
            "unexpected job error id=%s",
            job["id"],
        )

        await record_failure(worker_id, job)



async def main() -> None:

    pool = get_pool()

    await pool.open(
        wait=True,
        timeout=30,
    )

    log.info(
        "worker up (lease=%ss, poll=%ss)",
        LEASE_SECONDS,
        POLL_SECONDS,
    )

    worker_id = str(uuid4())

    log.info(
        "worker id=%s",
        worker_id,
    )


    try:

        while True:

            job = await claim_one_job(worker_id)

            if job is None:
                await asyncio.sleep(POLL_SECONDS)
                continue


            log.info(
                "claimed job id=%s attempt=%s/%s",
                job["id"],
                job["attempts"],
                job["max_attempts"],
            )


            await run_job(
                worker_id,
                job,
            )


    finally:

        await pool.close()



if __name__ == "__main__":
    asyncio.run(main())