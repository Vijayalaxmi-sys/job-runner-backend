"""FastAPI entrypoint.

`GET /health` is used by our grading harness to know when your stack is up —
please keep it working. Everything else is yours to build.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Response, status
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from app.db import get_pool


APPROVAL_COST_THRESHOLD = int(
    os.getenv("APPROVAL_COST_THRESHOLD", "100")
)


class CreateJobRequest(BaseModel):
    type: str
    payload: dict
    estimated_cost: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = get_pool()
    await pool.open(wait=True, timeout=30)

    yield

    await pool.close()


app = FastAPI(
    title="Job Runner",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    async with get_pool().connection() as conn:
        await conn.execute("SELECT 1")

    return {"status": "ok"}


@app.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(
    response: Response,
    request: CreateJobRequest,
    x_tenant_id: str = Header(...),
    idempotency_key: str = Header(...),
) -> dict:
    job_status = (
        "awaiting_approval"
        if request.estimated_cost > APPROVAL_COST_THRESHOLD
        else "queued"
    )

    job_id = uuid4()

    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                INSERT INTO jobs (
                    id,
                    tenant_id,
                    idempotency_key,
                    type,
                    payload,
                    estimated_cost,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                ON CONFLICT (tenant_id, idempotency_key)
                DO NOTHING
                RETURNING
                    id,
                    tenant_id,
                    type,
                    payload,
                    estimated_cost,
                    status,
                    attempts
                """,
                (
                    job_id,
                    x_tenant_id,
                    idempotency_key,
                    request.type,
                    Jsonb(request.payload),
                    request.estimated_cost,
                    job_status,
                ),
            )

            inserted_job = await cursor.fetchone()

            if inserted_job is not None:
                return {
                    "id": str(inserted_job["id"]),
                    "tenant_id": str(inserted_job["tenant_id"]),
                    "type": inserted_job["type"],
                    "payload": inserted_job["payload"],
                    "estimated_cost": inserted_job["estimated_cost"],
                    "status": inserted_job["status"],
                    "attempts": inserted_job["attempts"],
                }

            await cursor.execute(
                """
                SELECT
                    id,
                    tenant_id,
                    type,
                    payload,
                    estimated_cost,
                    status,
                    attempts
                FROM jobs
                WHERE tenant_id = %s
                  AND idempotency_key = %s
                """,
                (
                    x_tenant_id,
                    idempotency_key,
                ),
            )

            existing_job = await cursor.fetchone()

            if existing_job is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Existing job could not be found.",
                )

            same_request = (
                existing_job["type"] == request.type
                and existing_job["payload"] == request.payload
                and existing_job["estimated_cost"]
                == request.estimated_cost
            )

            if not same_request:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error": "idempotency_key_reuse",
                    },
                )

            response.status_code = status.HTTP_200_OK

            return {
                "id": str(existing_job["id"]),
                "tenant_id": str(existing_job["tenant_id"]),
                "type": existing_job["type"],
                "payload": existing_job["payload"],
                "estimated_cost": existing_job["estimated_cost"],
                "status": existing_job["status"],
                "attempts": existing_job["attempts"],
            }


@app.post("/jobs/{job_id}/approve")
async def approve_job(
    job_id: str,
    response: Response,
    x_tenant_id: str = Header(...),
):
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT
                    id,
                    status
                FROM jobs
                WHERE id = %s
                  AND tenant_id = %s
                """,
                (
                    job_id,
                    x_tenant_id,
                ),
            )

            job = await cursor.fetchone()

            if job is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "job_not_found"},
                )

            if job["status"] != "awaiting_approval":
                raise HTTPException(
                    status_code=409,
                    detail={"error": "job_not_awaiting_approval"},
                )

            await cursor.execute(
                """
                UPDATE jobs
                SET status = 'queued'
                WHERE id = %s
                  AND tenant_id = %s
                  AND status = 'awaiting_approval'
                RETURNING id, status
                """,
                (
                    job_id,
                    x_tenant_id,
                ),
            )

            approved_job = await cursor.fetchone()

            if approved_job is None:
                raise HTTPException(
                    status_code=409,
                    detail={"error": "job_not_awaiting_approval"},
                )

            return approved_job

@app.post("/jobs/{job_id}/reject")
async def reject_job(
    job_id: str,
    x_tenant_id: str = Header(...),
):
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:

            # Check whether the job exists
            await cursor.execute(
                """
                SELECT
                    id,
                    status
                FROM jobs
                WHERE id = %s
                  AND tenant_id = %s
                """,
                (
                    job_id,
                    x_tenant_id,
                ),
            )

            job = await cursor.fetchone()

            if job is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "job_not_found"},
                )

            # Only jobs awaiting approval can be rejected
            if job["status"] != "awaiting_approval":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "job_not_awaiting_approval"},
                )

            # Atomically reject the job
            await cursor.execute(
                """
                UPDATE jobs
                SET status = 'rejected'
                WHERE id = %s
                  AND tenant_id = %s
                  AND status = 'awaiting_approval'
                RETURNING id, status
                """,
                (
                    job_id,
                    x_tenant_id,
                ),
            )

            rejected_job = await cursor.fetchone()

            if rejected_job is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error": "job_not_awaiting_approval"},
                )

            return rejected_job
        
@app.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    x_tenant_id: str = Header(...),
) -> dict:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT
                    id,
                    tenant_id,
                    type,
                    payload,
                    estimated_cost,
                    status,
                    attempts,
                    created_at,
                    updated_at
                FROM jobs
                WHERE id = %s
                  AND tenant_id = %s
                """,
                (
                    job_id,
                    x_tenant_id,
                ),
            )

            job = await cursor.fetchone()

            if job is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "job_not_found"},
                )

            return {
                "id": str(job["id"]),
                "tenant_id": str(job["tenant_id"]),
                "type": job["type"],
                "payload": job["payload"],
                "estimated_cost": job["estimated_cost"],
                "status": job["status"],
                "attempts": job["attempts"],
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
            }
            
@app.get("/jobs")
async def list_jobs(
    status_filter: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    x_tenant_id: str = Header(...),
) -> dict:

    if limit < 1:
        limit = 20

    if limit > 100:
        limit = 100

    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cursor_db:

            query = """
                SELECT
                    id,
                    tenant_id,
                    type,
                    payload,
                    estimated_cost,
                    status,
                    attempts,
                    created_at,
                    updated_at
                FROM jobs
                WHERE tenant_id = %s
            """

            params = [x_tenant_id]

            if status_filter:
                query += """
                    AND status = %s
                """
                params.append(status_filter)

            if cursor:
                query += """
                    AND created_at < (
                        SELECT created_at
                        FROM jobs
                        WHERE id = %s
                    )
                """
                params.append(cursor)

            query += """
                ORDER BY created_at DESC
                LIMIT %s
            """

            params.append(limit)

            await cursor_db.execute(
                query,
                params,
            )

            jobs = await cursor_db.fetchall()

            return {
                "items": [
                    {
                        "id": str(job["id"]),
                        "tenant_id": str(job["tenant_id"]),
                        "type": job["type"],
                        "payload": job["payload"],
                        "estimated_cost": job["estimated_cost"],
                        "status": job["status"],
                        "attempts": job["attempts"],
                        "created_at": job["created_at"],
                        "updated_at": job["updated_at"],
                    }
                    for job in jobs
                ],
                "next_cursor": str(jobs[-1]["id"]) if jobs else None,
            }            
                   
# ── Your endpoints go here ───────────────────────────────────────────────
#
#   POST   /jobs
#   GET    /jobs
#   GET    /jobs/{job_id}
#   POST   /jobs/{job_id}/approve
#   POST   /jobs/{job_id}/reject