# Temporal Reminder API (minimal)

## Run
```bash
docker compose up --build
```
* API: http://localhost:8000/docs
* Temporal UI: http://localhost:8080

## Notes
* Reminders are Temporal **Schedules**.
* Each reminder also has a long-running **Record Workflow** to hold/persist metadata + Search Attributes for filtering.
* The Schedule starts a short **Fire Workflow** at each tick; it sends notifications via Apprise targets, then refreshes the record’s `ReminderNextFireTime` Search Attribute.

## Quick how-to

### Create a reminder

Create a one-time reminder using `spec.calendars`:

```bash
curl -X POST http://localhost:8000/reminders \
  -H 'content-type: application/json' \
  -d '{
    "title": "Test once (calendar)",
    "message": "fires at 2025-12-20T19:32:18Z",
    "tags": ["test"],
    "apprise_targets": ["ntfy://mytopic"],
    "spec": {
      "calendars": [{
        "year": [{"start": 2025}],
        "month": [{"start": 12}],
        "day_of_month": [{"start": 20}],
        "hour": [{"start": 19}],
        "minute": [{"start": 32}],
        "second": [{"start": 18}]
      }],
      "time_zone_name": "UTC"
    }
  }'
````

Create an interval reminder (every 5 minutes):

```bash
curl -X POST http://localhost:8000/reminders \
  -H 'content-type: application/json' \
  -d '{
    "title": "Hydrate",
    "message": "Drink water",
    "tags": ["health"],
    "apprise_targets": ["ntfy://mytopic"],
    "spec": {
      "intervals": [{"every": "PT5M"}],
      "time_zone_name": "UTC"
    }
  }'
```

### List reminders

List all reminders:

```bash
curl 'http://localhost:8000/reminders'
```

Filter by tag:

```bash
curl 'http://localhost:8000/reminders?tag=test'
```

Tokenized “contains-like” search (q is split into tokens and ANDed):

```bash
curl 'http://localhost:8000/reminders?q=trash%20pickup'
```

Filter upcoming reminders (and sort by next fire time):

```bash
curl 'http://localhost:8000/reminders?upcoming_after=2025-12-20T00:00:00Z&sort=next'
```

Append an advanced raw Temporal visibility clause:

```bash
curl 'http://localhost:8000/reminders?extra_filter=TaskQueue%20%3D%20%22reminders%22'
```

### Update a reminder

Update title/message/tags/targets and/or the Temporal schedule `spec`/`policies`/`state`:

```bash
RID="010439f6-f504-43b9-a399-63c95d0fc6ed"

curl -X PUT "http://localhost:8000/reminders/$RID" \
  -H 'content-type: application/json' \
  -d '{
    "title": "Updated title",
    "message": "Updated message",
    "tags": ["test", "updated"],
    "apprise_targets": ["ntfy://mytopic"],
    "spec": {
      "intervals": [{"every": "PT10M"}],
      "time_zone_name": "UTC"
    }
  }'
```

### Delete a reminder

Deletes the schedule `rem-{id}` and terminates the record workflow `record-{id}` (best-effort):

```bash
RID="010439f6-f504-43b9-a399-63c95d0fc6ed"
curl -X DELETE "http://localhost:8000/reminders/$RID"
```

### Inspect fire executions

List fire workflow executions:

```bash
curl 'http://localhost:8000/fires'
```

Filter by schedule id (Temporal default SA `TemporalScheduledById`):

```bash
SID="rem-010439f6-f504-43b9-a399-63c95d0fc6ed"
curl "http://localhost:8000/fires?scheduled_by_id=$SID"
```

Filter by scheduled start time (Temporal default SA `TemporalScheduledStartTime`):

```bash
curl 'http://localhost:8000/fires?after=2025-12-20T00:00:00Z'
```

### API docs

* Swagger UI: `http://localhost:8000/docs`
* OpenAPI JSON: `http://localhost:8000/openapi.json`
* ReDoc: `http://localhost:8000/redoc`


