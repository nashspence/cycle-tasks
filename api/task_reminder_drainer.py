import os
import asyncio
from datetime import datetime, timezone

import asyncpg
from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

TASK_QUEUE = os.getenv("TASK_QUEUE", "reminders")
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")

POSTGRES_URI = os.getenv("POSTGRES_URI")

POLL_SECONDS = float(os.getenv("OUTBOX_POLL_SECONDS", "1.0"))
BATCH_SIZE = int(os.getenv("OUTBOX_BATCH_SIZE", "200"))
CONCURRENCY = int(os.getenv("OUTBOX_CONCURRENCY", "50"))

WF_TYPE = "task_reminder"
WF_ID_PREFIX = "reminder-"  # reminder-{task_reminder_id}
SIGNAL = "set_fire_time"


def wf_id(reminder_id: int) -> str:
    return f"{WF_ID_PREFIX}{reminder_id}"


def iso_no_ms(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


def backoff_seconds(attempts: int) -> int:
    # 1,2,4,8,... up to 5 minutes
    return min(300, 2 ** max(0, attempts - 1))


CLAIM_SQL = """
with cte as (
  select id
  from api.reminder_outbox
  where processed_at is null
    and available_at <= now()
  order by id
  limit $1
  for update skip locked
)
update api.reminder_outbox o
set attempts = attempts + 1,
    available_at = now() + interval '30 seconds' -- short lease while we try
from cte
where o.id = cte.id
returning o.id, o.op, o.reminder_id, o.fire_at, o.attempts;
"""

MARK_OK_SQL = "update api.reminder_outbox set processed_at = now(), last_error = null where id = $1;"
MARK_FAIL_SQL = "update api.reminder_outbox set last_error = $2, available_at = now() + ($3 || ' seconds')::interval where id = $1;"


async def process_row(pg: asyncpg.Connection, temporal: Client, row) -> None:
    oid, op, rid, fire_at, attempts = row["id"], row["op"], row["reminder_id"], row["fire_at"], row["attempts"]

    try:
        if op == "upsert" and fire_at is not None:
            await temporal.start_workflow(
                WF_TYPE,
                int(rid),
                id=wf_id(int(rid)),
                task_queue=TASK_QUEUE,
                start_signal=SIGNAL,
                start_signal_args=[iso_no_ms(fire_at)],
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
                # Workflow completes after firing; allow reuse of same ID on future reschedules
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
            )
        else:
            # cancel (or unschedule) — simplest is cancel; ignore if missing
            try:
                await temporal.get_workflow_handle(wf_id(int(rid))).cancel()
            except Exception:
                pass

        await pg.execute(MARK_OK_SQL, oid)
    except Exception as e:
        await pg.execute(MARK_FAIL_SQL, oid, str(e), backoff_seconds(int(attempts)))


async def main() -> None:
    if not POSTGRES_URI:
        raise RuntimeError("POSTGRES_URI is required")

    temporal = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)
    pool = await asyncpg.create_pool(POSTGRES_URI, min_size=1, max_size=5)

    sem = asyncio.Semaphore(CONCURRENCY)

    async def _run_one(row):
        async with sem:
            async with pool.acquire() as pg:
                await process_row(pg, temporal, row)

    try:
        while True:
            async with pool.acquire() as pg:
                rows = await pg.fetch(CLAIM_SQL, BATCH_SIZE)

            if not rows:
                await asyncio.sleep(POLL_SECONDS)
                continue

            await asyncio.gather(*(_run_one(r) for r in rows))
    finally:
        await pool.close()
        await temporal.close()


if __name__ == "__main__":
    asyncio.run(main())
