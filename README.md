# Job Runner — scaffold

Plumbing only. No jobs table, no endpoints, no queue logic, no tests. That part is the task.

## Run it

```bash
make up          # postgres + migrations + api + 3 workers
curl localhost:8000/health
make logs        # follow api + worker logs
make psql        # psql shell into the database
make down        # stop and wipe the volume
```

Source is bind-mounted and the API runs with `--reload`, so edits are live.
Workers do not reload — restart them with `docker compose restart worker`.

## What's here

```
app/main.py        FastAPI app. /health only. Your endpoints go here.
app/worker.py      Worker process. Idles. Your queue loop goes here.
app/executor.py    PROVIDED, FROZEN. The "work" a job does. Do not modify.
app/db.py          Async connection pool. Adapt freely.
migrations/        0001 creates side_effects. Add 0002_, 0003_, ... for your schema.
scripts/migrate.py PROVIDED. Applies each .sql file once, in filename order.
```

## Rules

- **`app/executor.py` is frozen.** Don't edit it, don't wrap it in a way that
  skips it, don't reimplement it. It is the thing that must run exactly once.
- **`side_effects` keeps its name and columns.** You may add constraints and
  indexes to it from your own migrations.
- **Service names and ports are fixed**: `db`/`api`/`worker`, `5432`/`8000`.
  Our harness connects to them.
- **Keep `GET /health` working.** It's how we know your stack is up.
- Everything else — schema, project layout, libraries, patterns — is yours.

## Configuration

Read these from the environment; we set them ourselves when grading.

| Variable | Default | Meaning |
|---|---|---|
| `APPROVAL_COST_THRESHOLD` | `100` | Jobs with `estimated_cost` above this need approval |
| `JOB_LEASE_SECONDS` | `30` | How long a claim stays valid before another worker may take over |
| `EXECUTOR_FAILURE_RATE` | `0.2` | Probability that a single execution attempt fails |

## Tests

`pytest`, `pytest-asyncio` and `httpx` are already installed in the image.

```bash
make test        # runs pytest inside the api container
```

Where you put your tests is up to you.
