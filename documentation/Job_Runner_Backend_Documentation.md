**1. Project Overview**

Objective
The objective of this project is to design and implement a reliable asynchronous job processing backend capable of handling real-world distributed system challenges, including:
Duplicate client requests
Concurrent worker execution
Execution failures
Approval workflows
Worker interruptions and recovery scenarios
The system was implemented using:
FastAPI for API services
PostgreSQL for durable state management
Docker Compose for multi-service deployment
Asynchronous Python workers for background processing

The goal was to build a fault-tolerant job execution platform where jobs are created, processed, and completed safely under distributed system conditions.

**Primary Objectives**
The system ensures that jobs are:
Created reliably through API endpoints
Processed asynchronously by background workers
Executed without duplicate processing
Protected against duplicate external side effects
Recoverable after worker failures
Controlled through approval workflows when required
Problem Being Solved

In production distributed systems, simply creating a queue and running workers is not enough. Failures can occur at different points in the workflow and may result in duplicate processing, inconsistent states, or lost jobs.

This project addresses the following reliability challenges.

**1. Duplicate Job Submission**
Problem

Clients may submit the same request multiple times due to:

Network retries
Client timeout scenarios
User resubmission
API retry mechanisms
Without protection, duplicate requests could create multiple jobs and trigger duplicate processing.

**Solution Implemented**

The system implements idempotent job creation using:

tenant_id
idempotency_key

A database-level uniqueness constraint prevents duplicate job creation:

UNIQUE(tenant_id, idempotency_key)
Behavior

First request:

Create new job
Return 201 Created

Repeated request:

Return existing job
Return 200 OK

This ensures duplicate client requests do not create duplicate jobs.

**2. Concurrent Worker Processing**
Problem

Multiple workers may attempt to process available jobs simultaneously.

Without coordination:

Multiple workers could claim the same job
External systems could receive duplicate requests
Job state could become inconsistent

**Solution Implemented**

The worker system uses PostgreSQL row-level locking:

FOR UPDATE SKIP LOCKED

This provides atomic job claiming.

Result

Multiple workers can run concurrently while ensuring:

One worker owns a job at a time
Other workers skip locked jobs
Duplicate execution is prevented

**3. External Side Effect Duplication**
Problem
Jobs may interact with external systems such as:
Email providers
Payment systems
Notification services
Third-party APIs

A failure can happen after the external action completes but before the database update.
Example:

Worker starts execution
        |
External action succeeds
        |
Worker crashes before job completion update

A retry could incorrectly execute the external action again.

**Solution Implemented**

The system provides exactly-once side-effect protection using:

Existing side_effects table
Job-based uniqueness protection
Existing side-effect validation before retry execution

This prevents duplicate external effects during retries or worker failures.

**4. Approval Workflow Race Conditions**
Problem

Jobs above a configured cost threshold require approval.
Multiple users may attempt approval actions simultaneously.
Example:
User A → Approve
User B → Reject
User C → Approve

Without atomic state transitions, the job could reach an inconsistent state.

**Solution Implemented**

The system implements:

Approval state management
Atomic status transitions
Validation of current job state

Only valid transitions succeed.

Invalid concurrent actions return:

409 Conflict

Example:
job_not_awaiting_approval

**5. Worker Failure and Recovery**
Problem
Workers may stop unexpectedly because of:
Application crashes
Container failures
Network interruptions
Resource limitations
A job should not remain permanently stuck.

**Solution Implemented**

The worker system uses lease-based ownership:
leased_by
lease_until
Workflow:
Worker A claims job
        |
Worker A fails
        |
Lease expires
        |
Worker B reclaims job

Expired jobs can safely be processed again.

Reliability Goals

The system was designed around the following reliability principles.

**1. Exactly-Once Job Processing**

The system ensures a job is not processed multiple times even when:

Multiple workers are active
Requests are duplicated
Failures occur during execution
**2. Data Consistency**
PostgreSQL acts as the single source of truth.
Database transactions control:
Job states
Worker ownership
Approval transitions
Side-effect records
3. Fault Tolerance

The system continues operating when:
Workers fail
Requests are retried
External execution temporarily fails

**4. Safe Concurrency**

Multiple workers can execute simultaneously while preventing:

Duplicate job ownership
Race conditions
Invalid state transitions
**5. Verifiable Correctness**
Automated tests validate all reliability guarantees.
Final validation:
docker compose exec api pytest -q
Result:
6 passed

**2. System Architecture**
High-Level Architecture
Client
   |
   |
FastAPI API Service
   |
   |
PostgreSQL Database
   |
   |
Background Worker Processes
   |
   |
Executor
   |
   |
side_effects Table
Component Responsibilities
Component	Responsibility
FastAPI API	Job creation, status retrieval, approval/rejection APIs
PostgreSQL	Durable job state and consistency management
Worker Processes	Background job execution and recovery
Executor	Performs the actual job operation
side_effects Table	Prevents duplicate external effects

**3. Application Components**
app/main.py

Responsible for API functionality.

Implemented features:

Job creation endpoint
Job status retrieval
Approval endpoint
Rejection endpoint
Idempotency handling
Cost-based approval workflow
app/worker.py

Responsible for background processing.

Implemented features:

Job polling
Atomic job claiming
Worker leasing
Retry handling
Failed job recovery
Execution tracking
app/executor.py

The executor was provided as a frozen component.

Purpose:

Simulates external work execution
Must execute exactly once
Must not be modified or bypassed
app/db.py

Responsible for:

PostgreSQL asynchronous connection pool
Database access management
Shared database connectivity

**4. Database Design**
jobs Table

The jobs table stores complete job lifecycle information.

Column	Purpose
id	Unique job identifier
tenant_id	Tenant ownership
idempotency_key	Duplicate request prevention
type	Job category
payload	Job input data
estimated_cost	Determines approval requirement
status	Current lifecycle state
attempts	Retry tracking
max_attempts	Maximum allowed retries
leased_by	Worker ownership
lease_until	Worker lease expiration
side_effects Table

The provided side_effects table stores the results of external executions.

Additional protection:

UNIQUE(job_id)

Purpose:

Prevent duplicate side effects
Support recovery after worker failures
Guarantee exactly-once execution behavior
**5. Job Lifecycle**

Normal Execution
queued
   |
   v
running
   |
   v
succeeded
Failure Flow
running
   |
   v
failed
Approval Flow
queued
   |
   v
awaiting_approval
        |
        +------------+
        |            |
        v            v
   approved      rejected
   
**6. Reliability Guarantees**
**I1 - Idempotency**
Implementation

Protection against duplicate requests using:
tenant_id + idempotency_key
Database constraint:
UNIQUE(tenant_id,idempotency_key)
Tests
test_idempotency.py
test_idempotency_race.py
**I2 - Worker Concurrency**
Implementation
Workers claim jobs using:
FOR UPDATE SKIP LOCKED
This prevents multiple workers from owning the same job.

Test
test_worker_concurrency.py
**I3 - Exactly One Side Effect**
Implementation
Protection through:
side_effects table
unique job relationship
duplicate prevention checks
Test
test_side_effect.py
**I4 - Approval Race**
Implementation
Handles simultaneous approval/rejection requests through atomic status transitions.
Invalid transitions return:
409 Conflict
Test
test_approval.py
**I5 - Worker Recovery**
Implementation
Uses:
leased_by
lease_until
Expired jobs can be reclaimed by another worker.
Test
test_worker_recovery.py
7. Testing Evidence
Run Tests
docker compose exec api pytest -q
Result
6 passed
Test Coverage
Test	Purpose	Result
test_idempotency.py	Duplicate protection	PASS
test_idempotency_race.py	Concurrent requests	PASS
test_side_effect.py	Exactly once effect	PASS
test_approval.py	Approval race handling	PASS
test_worker_concurrency.py	Worker locking	PASS
test_worker_recovery.py	Crash recovery	PASS

**8. Running the System**
Start application:
docker compose up --build -d --scale worker=3
Run tests:
docker compose exec api pytest -q
**9. Design Decisions and Trade-offs**
**Why PostgreSQL?**
PostgreSQL provides:
Strong consistency
Transactions
Row-level locking
Durable state management
**Why Database Constraints?**
Database constraints provide protection even during:
Concurrent requests
Application retries
Race conditions
**Why Leases?**
Leases provide:
Worker ownership tracking
Crash recovery
Automatic job reclamation
**Why Row Locking?**
FOR UPDATE SKIP LOCKED provides:
Safe parallel workers
No duplicate ownership
High concurrency
