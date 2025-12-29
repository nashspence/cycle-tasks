import os
import json
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib import request, error

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import SearchAttributeKey, RetryPolicy

TASK_QUEUE = os.getenv("TASK_QUEUE", "reminders")
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")

# PostgREST base URL (service name "api" inside docker network)
API_UPSTREAM = os.getenv("API_UPSTREAM", "http://api:80").rstrip("/")

SA_ID = SearchAttributeKey.for_int("TaskReminderId")
SA_FIRE = SearchAttributeKey.for_datetime("TaskReminderFireTime")


def _parse_iso_utc(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _postgrest_rpc_fire(reminder_id: int) -> None:
    # PostgREST function endpoint: POST /rpc/fire_task_reminder  {"_reminder_id": 123}
    url = f"{API_UPSTREAM}/rpc/fire_task_reminder"
    data = json.dumps({"_reminder_id": reminder_id}).encode("utf-8")

    req = request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Ask PostgREST to return something if you want; not required for void
            # "Prefer": "return=minimal",
        },
    )

    # IMPORTANT: urllib timeout is connect+read; keep it < Temporal activity timeout
    with request.urlopen(req, timeout=10) as resp:
        # PostgREST often returns 204 for void RPC; 200 can also happen depending on settings
        if resp.status not in (200, 201, 204):
            raise RuntimeError(f"PostgREST RPC failed: {resp.status}")


@activity.defn
async def fire_task_reminder(task_reminder_id: int) -> None:
    # Run blocking urllib in a thread so the activity stays async-friendly
    try:
        await asyncio.to_thread(_postgrest_rpc_fire, task_reminder_id)
    except error.HTTPError as e:
        # surface useful error
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise RuntimeError(f"PostgREST HTTPError {e.code}: {body}") from e
    except Exception as e:
        raise


@workflow.defn(name="task_reminder")
class TaskReminderWorkflow:
    def __init__(self) -> None:
        self.rid: Optional[int] = None
        self.fire_at: Optional[datetime] = None
        self._dirty = False

    @workflow.run
    async def run(self, task_reminder_id: int) -> None:
        self.rid = task_reminder_id
        workflow.upsert_search_attributes([SA_ID.value_set(task_reminder_id)])

        while True:
            if not self.fire_at:
                await workflow.wait_condition(lambda: self._dirty)
                self._dirty = False
                continue

            workflow.upsert_search_attributes([
                SA_ID.value_set(self.rid),
                SA_FIRE.value_set(self.fire_at),
            ])

            now = workflow.now().astimezone(timezone.utc)
            delay = max(self.fire_at - now, timedelta(seconds=0))

            self._dirty = False
            try:
                await workflow.wait_condition(lambda: self._dirty, timeout=delay)
                if self._dirty:
                    continue
            except TimeoutError:
                pass  # time to fire

            await workflow.execute_activity(
                fire_task_reminder,
                self.rid,
                start_to_close_timeout=timedelta(seconds=20),
                schedule_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=20),
                    maximum_attempts=10,
                ),
            )
            return

    @workflow.signal
    def set_fire_time(self, fire_time_iso: Optional[str]) -> None:
        self.fire_at = _parse_iso_utc(fire_time_iso) if fire_time_iso else None
        self._dirty = True


async def main() -> None:
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)
    from temporalio.worker import Worker

    await Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TaskReminderWorkflow],
        activities=[fire_task_reminder],
    ).run()


if __name__ == "__main__":
    asyncio.run(main())
