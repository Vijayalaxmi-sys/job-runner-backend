**1. Project Overview**
Objective

The objective of this project is to design and implement a reliable asynchronous job processing backend capable of handling real-world distributed system challenges such as duplicate requests, concurrent worker execution, execution failures, approval workflows, and worker interruptions.

The system was built using FastAPI, PostgreSQL, Docker Compose, and asynchronous Python workers to provide a durable and fault-tolerant job execution platform.

The primary goal was to ensure that jobs are:

Created reliably through an API interface
Processed asynchronously by background workers
Executed safely without duplicate processing
Protected against duplicate external side effects
Recoverable after worker failures
Controlled through approval workflows when required
Problem Being Solved

In a production job processing system, simply creating a queue and running workers is not sufficient. Distributed systems introduce several failure scenarios that must be handled correctly.

This project addresses the following engineering challenges:

**1. Duplicate Job Submission**
Clients may send the same request multiple times due to:
Network retries
Client timeout issues
User resubmission
API retry mechanisms
Without protection, duplicate requests could create duplicate jobs and cause unintended processing.
Solution implemented:
Added idempotency handling using tenant_id and idempotency_key
Enforced database-level uniqueness constraints
Returned existing jobs for repeated requests instead of creating duplicates

**2. Concurrent Worker Processing**
Multiple workers may attempt to process available jobs at the same time.
Without proper coordination:
The same job could be executed by multiple workers
External systems could receive duplicate requests
Data consistency could be compromised
Solution implemented:
Used PostgreSQL row-level locking
Implemented atomic job claiming using:
FOR UPDATE SKIP LOCKED
This allows multiple workers to operate concurrently while ensuring that each job is owned by only one worker at a time.

**3. External Side Effect Duplication**
Job execution may interact with external systems such as:
Email providers
Payment systems
Notification services
Third-party APIs
A worker could fail after completing the external action but before updating the database.
Example scenario:
Worker starts execution
        |
External action succeeds
        |
Worker crashes before marking job complete
A retry could incorrectly execute the external action again.
Solution implemented:
Added side-effect tracking
Used the provided side_effects table
Added uniqueness protection using job identifiers
Checked existing side effects before retrying execution

**4. Approval Workflow Race Conditions**
Certain jobs require manual approval before execution based on cost thresholds.
Multiple users may attempt approval actions simultaneously:
Example:
User A → Approve
User B → Reject
User C → Approve
Without atomic state transitions, the job could reach an inconsistent state.
Solution implemented:
Added approval state management
Allowed only valid state transitions
Returned conflict responses (409) for invalid concurrent approval attempts

**5. Worker Failure and Recovery**
Background workers may stop unexpectedly because of:
Application crashes
Container failures
Network issues
Resource limitations
A job being processed by a failed worker should not remain permanently stuck.
Solution implemented:
Added worker lease management:
leased_by
lease_until
Allowed expired jobs to be reclaimed by another worker
Implemented recovery testing to verify failed worker scenarios
Reliability Goals
The system was designed around the following reliability principles:
1. Exactly-Once Job Processing
Ensure that a single job is not processed multiple times even when:
Multiple workers are active
Requests are duplicated
Failures occur during execution
2. Data Consistency

Maintain a single source of truth using PostgreSQL transactions.
The database controls:
Job states
Worker ownership
Approval transitions
Side-effect records
3. Fault Tolerance
The system should continue operating even when:

Workers fail
Requests are retried
External execution fails temporarily
4. Safe Concurrency
Enable multiple workers to run simultaneously while preventing:
Duplicate job ownership
Race conditions
Inconsistent state updates
5. Verifiable Correctness
The implementation includes automated tests covering all major reliability guarantees:

Idempotency protection
Concurrent request handling
Worker concurrency
Exactly-once side effects
Approval race handling
Worker recovery
Final validation:
docker compose exec api pytest -q
Result:
6 passed

**2. System Architecture**
High-level architecture diagram
Component responsibilities

Example:

Client
 |
FastAPI API
 |
PostgreSQL
 |
Worker Processes
 |
Executor
 |
side_effects
3. Application Components
app/main.py

Explain:

API endpoints
Job creation
Status checking
Approval/rejection endpoints
app/worker.py

Explain:

Job polling
Claiming logic
Lease handling
Retry handling
app/executor.py

Explain:

Provided frozen executor
Exactly once execution requirement
app/db.py

Explain:

Async connection pool
Database access pattern
4. Database Design

Detailed explanation:

jobs table

Columns:

id
tenant_id
idempotency_key
type
payload
estimated_cost
status
attempts
max_attempts
leased_by
lease_until

Purpose of each column.

side_effects table

Explain:

Existing provided table
Added constraint
Exactly once protection
5. Job Lifecycle

Explain all states:

queued
 |
running
 |
succeeded

Failure:

running
 |
failed

Approval:

queued
 |
awaiting_approval
 |
approved/rejected
6. Reliability Guarantees

This is the most important section.

I1 - Idempotency

Explain:

duplicate requests
unique constraint
race handling

Test:

test_idempotency.py
test_idempotency_race.py
I2 - Worker Concurrency

Explain:

FOR UPDATE SKIP LOCKED

Why it prevents duplicate ownership.

Test:

test_worker_concurrency.py
I3 - Exactly One Side Effect

Explain:

provider execution
side_effects table
duplicate prevention

Test:

test_side_effect.py
I4 - Approval Race

Explain:

multiple approve/reject requests
atomic status transition
409 conflicts

Test:

test_approval.py
I5 - Worker Recovery

Explain:

worker crash scenario
lease expiration
reclaiming

Test:

test_worker_recovery.py
7. Testing Evidence

Include:

Command:

docker compose exec api pytest -q

Output:

6 passed

Table:

Test	Purpose	Result
test_idempotency	Duplicate protection	PASS
test_idempotency_race	Concurrent requests	PASS
test_side_effect	Exactly once effect	PASS
test_approval	Approval race	PASS
test_worker_concurrency	Worker locking	PASS
test_worker_recovery	Crash recovery	PASS
8. Running the System

Commands:

docker compose up --build -d --scale worker=3
docker compose exec api pytest -q
9. Design Decisions and Trade-offs

Explain:

Why PostgreSQL
Why database constraints
Why leases
Why row locking
