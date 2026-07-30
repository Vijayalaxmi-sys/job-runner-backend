"""PROVIDED — DO NOT MODIFY THIS FILE.

This stands in for the real work a job performs: calling a third-party
provider that charges money and cannot be un-called.

It is deliberately NOT idempotent. Every successful call appends a row to
`side_effects`. Guaranteeing that a job ends up with exactly one such row —
across retries, across three concurrent workers, across a worker being
killed mid-flight — is your problem, not this file's.

The INSERT below runs on the connection you hand in, so it participates in
whatever transaction that connection is currently in.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
from uuid import UUID

from psycopg import AsyncConnection

FAILURE_RATE = float(os.getenv("EXECUTOR_FAILURE_RATE", "0.2"))


class TransientExecutionError(RuntimeError):
    """The provider failed. Retrying may succeed."""


async def execute(
    conn: AsyncConnection,
    job_id: UUID | str,
    job_type: str,
    payload: dict,
) -> dict:
    # The provider takes a while to respond.
    await asyncio.sleep(random.uniform(0.4, 1.6))

    if random.random() < FAILURE_RATE:
        raise TransientExecutionError(f"provider rejected job {job_id}")

    result = {
        "job_type": job_type,
        "items_processed": len(payload.get("items", [])),
        "receipt": f"rcpt_{random.randrange(16 ** 8):08x}",
    }

    await conn.execute(
        "INSERT INTO side_effects (job_id, payload) VALUES (%s, %s)",
        (str(job_id), json.dumps(result)),
    )

    # The provider's acknowledgement round-trip. Whatever happens to this
    # process during this window is yours to survive.
    await asyncio.sleep(0.3)

    return result
