# Operational Incident Runbooks

This runbook helps on-call engineers diagnose and mitigate production incidents in the URL Shortener & Collaboration Service under stress.

---

## 1. Incident Symptom Classifier (Decision Tree)

Start here to classify the symptom and route to the correct runbook:

```
                     [ START: INCIDENT DETECTED ]
                                  │
          Is the primary symptom HTTP error responses (5xx)?
          ├── YES ──────> Are users seeing 500/503 errors on /ready or /r/{code}?
          │               └── YES ───> [Go to RUNBOOK 1: High Error Rate]
          │
          └── NO ───────> Is the primary symptom high request latency (>1.5s)?
                          ├── YES ───> [Go to RUNBOOK 2: Request Latency Spike]
                          │
                          └── NO ────> Are link creations failing or is count low?
                                       └── YES ───> [Go to RUNBOOK 3: Store Failure]
                                       └── NO ────> [Go to Section 5: Escalation]
```

---

## 2. RUNBOOK 1: High Error Rate (Database Connection Failure)

### Alert / Detection
- **Alert Name**: `High Error Rate`
- **Threshold**: `5xx HTTP error rate > 5% for >2 minutes`
- **Symptoms**: Users receive `500 Internal Server Error` or `503 Service Unavailable` on redirect and management routes. Slack notifications alert for failing `/ready` endpoint probes.

### Diagnosis
Follow these verification steps in order:

#### Step 1: Query the liveness check
Verify if the application process itself is running:
```powershell
curl.exe -i -fsS http://localhost:8000/live
```
- **If process is healthy (Yes, it is running)**: Returns HTTP `200 OK` with:
  ```json
  {"status": "healthy"}
  ```
- **If process is dead (No, it is not running)**: Returns connection refused:
  ```
  curl: (7) Failed to connect to localhost port 8000: Connection refused
  ```
  *Action*: If the process is dead, go straight to **Fix Step 1 (Restart)**.

#### Step 2: Query the readiness check
Determine if the application can reach its backing databases:
```powershell
curl.exe -i http://localhost:8000/ready
```
- **If database is unreachable (Yes, this is the problem)**: Returns HTTP `503 Service Unavailable` with:
  ```json
  {"error":{"code":"HTTP_ERROR","message":"Database connection failed","request_id":"..."}}
  ```
- **If database is healthy (No, this is not the problem)**: Returns HTTP `200 OK` with:
  ```json
  {"status": "ready"}
  ```

#### Step 3: Run database connectivity check from the application engine
Run this command on the host (which dynamically uses the configured `DATABASE_URL`):
```powershell
python -c "import asyncio, os; from sqlalchemy.ext.asyncio import create_async_engine; from sqlalchemy import text; engine = create_async_engine(os.getenv('DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@localhost:5432/postgres')); asyncio.run(engine.connect())"
```
- **If database is down**: Throws a `ConnectionRefusedError` or `TimeoutError`:
  ```
  ConnectionRefusedError: [WinError 1225] The remote computer refused the network connection
  ```
- **If database is up**: Completes silently with no output.

### Fix
Follow these mitigation steps in order:

#### Step 1: Check Database Status and Start Postgres
Verify if PostgreSQL is running locally or in your target environment. If it is stopped, start it:
```powershell
# In a local Windows environment with PostgreSQL service installed:
Start-Service -Name "postgresql*"

# If running via Docker:
docker start postgres
```
- **Expected Output**: PostgreSQL service enters `Running` state.

#### Step 2: Restart the API Service
If the database connection pool got exhausted, restart the application to clear connections:
```powershell
# Restart local Uvicorn process
Stop-Process -Name "python" -Force
uvicorn app.main:app --reload --port 8000
```
- **Expected Output**:
  ```
  INFO:     Started server process [1234]
  INFO:     Waiting for application startup.
  INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
  ```

### Verification
Confirm the fix worked:
```powershell
curl.exe -fsS http://localhost:8000/ready
```
- **Expected Output**: `{"status": "ready"}`
- Wait 2 minutes and execute again. Ensure it remains `ready` and check that error metrics drop on the dashboard.

### Escalation
If `/ready` still returns 503 after starting the database and restarting the service:
1. Document the exact error message and the output of the python database check.
2. Page the Primary On-Call: John Doe (+1-555-0199) or via PagerDuty.

---

## 3. RUNBOOK 2: Request Latency Spike (Database Query Latency)

### Alert / Detection
- **Alert Name**: `Request Latency Spike`
- **Threshold**: `95th percentile request latency > 1.5 seconds for >2 minutes`
- **Symptoms**: Page loads feel sluggish. Redirects scale up past 1 second. Dashboards show a spike in response times.

### Diagnosis
Follow these verification steps in order:

#### Step 1: Inspect Prometheus metrics endpoint for slow routes
```powershell
curl.exe -s http://localhost:8000/metrics
```
Filter for latency bucket counts:
```powershell
curl.exe -s http://localhost:8000/metrics | Select-String "http_request_duration_seconds_sum"
```
- **If problem (Slow endpoints exist)**: Look for values where the sum divided by the count is high (>1.5s), for example:
  ```
  http_request_duration_seconds_sum{method="GET",path="/links/",status="200"} 45.2
  http_request_duration_seconds_count{method="GET",path="/links/",status="200"} 15
  ```
  (Average latency = 45.2 / 15 = 3.01 seconds)
- **If healthy**: All calculations result in values < 0.2 seconds.

#### Step 2: Inspect connection pool utilization and query logs
Check if queries are taking longer than the configured timeout `DB_QUERY_TIMEOUT_SECONDS` (default is 2.0s). Look for the following string in logs:
```powershell
Get-Content -Path "app.log" -Tail 100 | Select-String "Database operation timed out"
```
- **If timeout is occurring**: Returns log lines showing query timeouts.

### Fix
Follow these mitigation steps in order:

#### Step 1: Temporarily decrease the query timeout limit
Reduce the query timeout to fail fast, preserving service worker capacity:
```powershell
$env:DB_QUERY_TIMEOUT_SECONDS = "1.0"
# Restart application to pick up environment variable
Stop-Process -Name "python" -Force
uvicorn app.main:app --reload --port 8000
```
- **Expected Output**: Slow queries will be aborted at 1.0s, returning `503 Database Timeout` to the client instead of hanging the thread pool.

#### Step 2: Check for N+1 Query patterns or missing database indexes
Verify that `test_links_endpoint` is using joined eager loading (`joinedload` on relationships) rather than executing separate queries for each record.

### Verification
Confirm the latency drops:
```powershell
curl.exe -s http://localhost:8000/metrics | Select-String "http_request_duration_seconds_sum"
```
- Verify that average latency drops below 200ms.

### Escalation
If average latency remains > 1.5s:
1. Document the slow endpoint paths identified from `/metrics`.
2. Page the Primary On-Call: John Doe (+1-555-0199) or via PagerDuty.

---

## 4. RUNBOOK 3: Link Count Drop or Store Failure (Redis Cache / Queue Outage)

### Alert / Detection
- **Alert Name**: `Link Count Drop or Store Failure`
- **Threshold**: `url_shortener_links_current_count < 100` or `POST /links/ failures`
- **Symptoms**: Click events are not displaying in the analytics dashboard. Redis connection timeouts logged. Cache invalidations on patch/delete fail.

### Diagnosis
Follow these verification steps in order:

#### Step 1: Query the readiness check for Redis status
```powershell
curl.exe -i http://localhost:8000/ready
```
- **If Redis is down (Yes, this is the problem)**: Returns HTTP `503 Service Unavailable` with:
  ```json
  {"error":{"code":"HTTP_ERROR","message":"Redis connection failed","request_id":"..."}}
  ```

#### Step 2: Run Redis ping check from host
```powershell
python -c "import asyncio; from redis.asyncio import from_url; client = from_url('redis://localhost:6379'); asyncio.run(client.ping())"
```
- **If Redis is unreachable**: Raises a `ConnectionError` or `TimeoutError`:
  ```
  redis.exceptions.ConnectionError: Error 10061 connecting to localhost:6379. Connection refused.
  ```
- **If Redis is healthy**: Returns `True`.

### Fix
Follow these mitigation steps in order:

#### Step 1: Verify and start Redis Service
If Redis is stopped, start it:
```powershell
# On Windows (if installed as a service):
Start-Service -Name "redis*"

# If running via Docker:
docker start redis
```
- **Expected Output**: Redis service enters running state.

#### Step 2: Clear/Reset the Cache circuit breaker
The service has a circuit breaker. Once Redis is recovered, verify it returns to closed state by querying readiness.

### Verification
Confirm Redis is healthy and the circuit breaker closed:
```powershell
curl.exe -fsS http://localhost:8000/ready
```
- **Expected Output**: `{"status": "ready"}`
- Wait 2 minutes and execute again. Verify the circuit breaker logs do not show open warnings.

### Escalation
If Redis is healthy but store failures continue:
1. Check database write locks or disk space.
2. Page the Primary On-Call: John Doe (+1-555-0199) or via PagerDuty.
