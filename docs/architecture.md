# PlayerPulse Architecture

# 1. Purpose

This document describes the technical architecture of PlayerPulse.

Its goals are to:

- explain how data moves through the platform;
- define the responsibility of each component;
- document important architectural decisions;
- distinguish the current implementation from future improvements;
- provide a reusable reference architecture for future API-driven data engineering projects.

PlayerPulse currently implements the following pattern:

```text
External API
    ↓
Python Ingestion
    ↓
Raw Files
    ↓
Cloud Object Storage
    ↓
Cloud Data Warehouse
    ↓
SQL Transformation
    ↓
Data Quality Tests
    ↓
Analytics-Ready Models
```

The specific source is Chess.com, but the architecture is intentionally designed so the source system could later be replaced.

---

# 2. System Context

At the highest level, PlayerPulse connects an external public API to an analytical warehouse.

```mermaid
flowchart LR

    USER[Developer / Analyst]
    API[Chess.com Public API]
    PIPELINE[PlayerPulse Data Pipeline]
    AWS[AWS S3]
    SNOW[Snowflake]
    ANALYTICS[Analytics Consumer]

    USER -->|runs / monitors| PIPELINE
    API -->|JSON over HTTPS| PIPELINE
    PIPELINE -->|raw files| AWS
    AWS -->|external stage / COPY| SNOW
    SNOW -->|analytics-ready data| ANALYTICS
```

The system currently runs from a local Docker environment.

AWS S3 and Snowflake are cloud services.

---

# 3. High-Level Architecture

```mermaid
flowchart LR

    subgraph SOURCE["Source System"]
        API[Chess.com Public API]
    end

    subgraph LOCAL["Local / Docker Environment"]
        AIRFLOW[Apache Airflow]
        PYTHON[Python Scripts]
        RAWLOCAL[Local Raw JSON]
        PROCESSED[Local Processed JSONL]
        DBT[dbt Core]
    end

    subgraph AWS["AWS"]
        S3[AWS S3 Raw Storage]
        IAM[AWS IAM]
    end

    subgraph SNOWFLAKE["Snowflake"]
        STAGE[External Stage]
        RAW[RAW Schema]
        STAGING[STAGING Schema]
        MARTS[MARTS Schema]
    end

    API --> PYTHON
    AIRFLOW --> PYTHON

    PYTHON --> RAWLOCAL
    RAWLOCAL --> PROCESSED
    RAWLOCAL --> S3

    IAM --> S3

    S3 --> STAGE
    STAGE --> RAW

    RAW --> DBT
    DBT --> STAGING
    STAGING --> MARTS
```

An important detail is that the locally processed JSONL files are **not currently the source used for the Snowflake load**.

The cloud path uses the raw Chess.com JSON files:

```text
Chess.com API
    ↓
Raw JSON
    ↓
S3
    ↓
Snowflake RAW
```

The local JSONL transformation exists as a separate learning and processing layer.

---

# 4. Control Flow vs Data Flow

One of the most important architectural distinctions in PlayerPulse is the difference between:

```text
control flow
```

and:

```text
data flow
```

## Control flow

Airflow controls **when tasks run**.

```mermaid
flowchart TD

    T1[fetch_player_profile]
    T2[fetch_player_games]
    T3[transform_all_games]
    T4[upload_games_to_s3]
    T5[load_snowflake_raw]
    T6[dbt_build]

    T1 --> T2
    T2 --> T3
    T3 --> T4
    T4 --> T5
    T5 --> T6
```

Airflow does not itself contain the game data.

It coordinates the programs that process the data.

---

## Data flow

The actual data travels through a different conceptual path:

```mermaid
flowchart LR

    API[Chess.com API]
    JSON[Raw JSON]
    S3[S3]
    ARCHIVES[RAW.GAME_ARCHIVES]
    GAMES[RAW.GAMES]
    STG[STAGING.STG_GAMES]
    MART[MARTS.FCT_PLAYER_GAMES]

    API --> JSON
    JSON --> S3
    S3 --> ARCHIVES
    ARCHIVES --> GAMES
    GAMES --> STG
    STG --> MART
```

This distinction matters because an orchestration system and a storage system solve different problems.

---

# 5. Component Responsibilities

| Component | Primary Responsibility | Does Not Replace |
|---|---|---|
| Chess.com API | Expose public source data | Storage or transformation |
| Python | Procedural ingestion and file processing | Workflow orchestration |
| Airflow | Task orchestration and dependency management | Data warehouse |
| Docker | Reproducible runtime environment | Orchestration |
| AWS S3 | Durable raw object storage | Analytical database |
| AWS IAM | Authentication and authorization | Data storage |
| Snowflake | Analytical data storage and SQL compute | Raw object storage |
| dbt | SQL modeling, testing, lineage | Workflow engine |
| Git | Source version control | Data storage |
| GitHub | Repository hosting and collaboration | Runtime infrastructure |

A major design principle is:

> Give each technology a clear responsibility.

---

# 6. Source Layer

## Chess.com Public API

The source system exposes public resources through HTTPS.

Important endpoints include:

```text
/pub/player/{username}

/pub/player/{username}/games/archives

/pub/player/{username}/games/{year}/{month}
```

The source data is JSON.

Example conceptual structure:

```json
{
  "games": [
    {
      "uuid": "...",
      "time_class": "rapid",
      "white": {
        "username": "...",
        "rating": 1200,
        "result": "win"
      },
      "black": {
        "username": "...",
        "rating": 1190,
        "result": "resigned"
      }
    }
  ]
}
```

The ingestion layer preserves this original representation before warehouse modeling.

---

# 7. Python Ingestion Layer

Python is used when procedural logic is required.

Examples include:

- HTTP requests;
- looping over available archives;
- parsing archive URLs;
- reading and writing files;
- retry/error handling;
- S3 SDK calls;
- Snowflake connector calls.

The scripts are separated by responsibility.

```text
scripts/
├── fetch_player_profile.py
├── fetch_player_games.py
├── transform_games.py
├── transform_all_games.py
├── upload_to_s3.py
├── upload_all_to_s3.py
└── load_s3_to_snowflake.py
```

This separation allows individual components to be tested independently.

---

# 8. Archive Discovery

The ingestion process does not assume that every month contains games.

It first requests:

```text
/pub/player/{username}/games/archives
```

The API returns only the archive URLs that actually exist.

The pipeline then loops over those available archives.

Conceptually:

```text
Ask API which archives exist
        ↓
Receive list of URLs
        ↓
Loop through URLs
        ↓
Download each archive
```

This is preferable to blindly generating every year/month combination.

---

# 9. Local Raw Storage

Downloaded API responses are initially written to:

```text
data/raw/
```

Example:

```text
data/raw/ajaza_games_2026_03.json
```

Local raw data is not committed to Git.

Reasons include:

- source data should not unnecessarily inflate the repository;
- raw files can be regenerated;
- code and data have different lifecycle requirements;
- the cloud raw layer is S3.

---

# 10. Local Processing Layer

The project also contains Python logic that converts nested JSON into flattened JSON Lines.

Conceptually:

```text
Nested API JSON
       ↓
Python flattening
       ↓
JSONL
```

Example:

```text
white.username
```

becomes:

```text
white_username
```

The output is written under:

```text
data/processed/
```

## Architectural note

This local transformation currently does not feed Snowflake.

The Snowflake path intentionally starts from the raw JSON stored in S3.

That means PlayerPulse currently demonstrates two transformation approaches:

### File-level transformation

```text
JSON
→ Python
→ JSONL
```

### Warehouse transformation

```text
Raw JSON
→ Snowflake VARIANT
→ SQL/dbt
```

The warehouse-based approach is the primary analytical architecture.

---

# 11. Airflow Orchestration Layer

Apache Airflow is the workflow orchestrator.

Current DAG:

```text
dags/playerpulse_pipeline.py
```

Current execution graph:

```text
fetch_player_profile
        ↓
fetch_player_games
        ↓
transform_all_games
        ↓
upload_games_to_s3
        ↓
load_snowflake_raw
        ↓
dbt_build
```

Airflow provides:

- dependency management;
- task state;
- retries;
- centralized logs;
- manual triggering;
- scheduling capability;
- failure visibility.

---

# 12. Why Airflow Is Separate From Python

The Python scripts are independently executable.

For example:

```bash
python3 scripts/fetch_player_games.py ajaza --all
```

Airflow does not replace this Python code.

Instead, Airflow invokes the scripts and coordinates their order.

Without Airflow:

```text
Developer manually runs command 1
Developer manually runs command 2
Developer manually runs command 3
...
```

With Airflow:

```text
DAG defines dependencies
        ↓
Airflow executes tasks
        ↓
Airflow tracks success/failure
```

This separation improves maintainability and automation.

---

# 13. Raw Cloud Storage

AWS S3 acts as the durable raw storage layer.

Current conceptual structure:

```text
s3://<bucket>/
└── chesscom/
    └── games/
        └── username=ajaza/
            ├── year=2018/
            │   └── month=11/
            │       └── games.json
            │
            └── year=2026/
                ├── month=01/
                │   └── games.json
                └── month=03/
                    └── games.json
```

The path uses partition-style keys:

```text
username=<value>
year=<value>
month=<value>
```

This provides a predictable storage convention.

---

# 14. Why Keep a Raw Layer?

A raw layer provides a stable copy of source data.

If downstream transformation logic changes, the original API response remains available.

Without a raw layer:

```text
API
 ↓
Transformation
 ↓
Final table
```

If the transformation was wrong, the source may need to be downloaded again.

With a raw layer:

```text
API
 ↓
S3 RAW
 ↓
Transformation v1

S3 RAW
 ↓
Transformation v2
```

The same source can be replayed.

---

# 15. AWS Security Boundary

PlayerPulse separates AWS authentication from application source code.

The source repository does not contain AWS secret keys.

For local development:

```text
Host ~/.aws
    ↓ read-only mount
Airflow container
    ↓
AWS SDK / boto3
    ↓
AWS
```

The Docker mount is:

```text
${HOME}/.aws:/home/airflow/.aws:ro
```

The `ro` flag means:

```text
read only
```

The container can use the credentials but cannot modify the host AWS configuration.

---

# 16. IAM Authorization

A dedicated IAM identity is used by the pipeline.

Its permissions are limited to the required S3 operations.

Examples include:

```text
s3:GetBucketLocation
s3:ListBucket
s3:GetObject
s3:PutObject
```

This follows the principle of:

```text
least privilege
```

meaning an application should receive only the permissions required to perform its job.

---

# 17. Snowflake–AWS Trust Relationship

Snowflake accesses S3 through a Storage Integration.

Conceptually:

```mermaid
flowchart LR

    SNOW[Snowflake]
    INT[Storage Integration]
    ROLE[AWS IAM Role]
    BUCKET[S3 Bucket]

    SNOW --> INT
    INT --> ROLE
    ROLE --> BUCKET
```

This avoids embedding an AWS access key directly inside Snowflake.

---

# 18. External Stage

Snowflake uses an external stage to reference the S3 location.

Conceptually:

```text
Snowflake Stage
      ↓
s3://<bucket>/chesscom/
```

A stage is metadata describing where the external files are located and how Snowflake can access them.

The stage is not itself another copy of the source files.

---

# 19. Snowflake Logical Architecture

The database is separated into three logical schemas:

```text
PLAYERPULSE
│
├── RAW
├── STAGING
└── MARTS
```

Each layer has a different purpose.

---

# 20. RAW Layer

The RAW schema keeps data close to its original source form.

Current objects include:

```text
RAW.GAME_ARCHIVES
RAW.GAMES
```

## GAME_ARCHIVES

Each row represents one monthly source file.

Conceptual columns:

```text
SOURCE_FILE
LOADED_AT
PAYLOAD
```

`PAYLOAD` uses Snowflake:

```text
VARIANT
```

which supports semi-structured JSON.

---

# 21. JSON Flattening in Snowflake

A monthly archive contains:

```text
one file
    ↓
games array
    ↓
many game objects
```

Snowflake uses:

```sql
LATERAL FLATTEN
```

to turn the array into one row per game.

Conceptually:

```text
GAME_ARCHIVES

archive_1 → [game1, game2, game3, game4]
archive_2 → [game5]

            ↓ LATERAL FLATTEN

RAW.GAMES

game1
game2
game3
game4
game5
```

This is a common pattern when loading nested JSON into an analytical warehouse.

---

# 22. Snowflake Compute

Snowflake separates:

```text
storage
```

from:

```text
compute
```

The database stores persistent data.

The virtual warehouse executes queries.

Current compute resource:

```text
PLAYERPULSE_WH
```

The warehouse uses a small size and automatic suspension.

This helps reduce unnecessary compute usage.

---

# 23. Snowflake Raw Load Process

The automated loader:

```text
scripts/load_s3_to_snowflake.py
```

performs the following steps:

```mermaid
flowchart TD

    START[Start]
    SCHEMA[Ensure RAW schema exists]
    STAGE[Ensure external stage exists]
    TABLE[Ensure GAME_ARCHIVES exists]
    TRUNCATE[Truncate raw archive table]
    COPY[COPY S3 files into Snowflake]
    FLATTEN[Build RAW.GAMES]
    VALIDATE[Validate game uniqueness]
    END[Complete]

    START --> SCHEMA
    SCHEMA --> STAGE
    STAGE --> TABLE
    TABLE --> TRUNCATE
    TRUNCATE --> COPY
    COPY --> FLATTEN
    FLATTEN --> VALIDATE
    VALIDATE --> END
```

---

# 24. Current Loading Strategy

The current implementation uses:

```text
full refresh
```

rather than:

```text
incremental loading
```

The raw archive table is cleared and rebuilt from the current S3 contents.

This is appropriate for the current dataset size.

Current sample:

```text
10 games
```

The architecture favors correctness and simplicity before introducing incremental state management.

---

# 25. Idempotency

A key property of the current pipeline is rerunnability.

If the pipeline is run several times against the same source:

```text
Run 1 → 10 games
Run 2 → 10 games
Run 3 → 10 games
```

It should not create:

```text
Run 1 → 10
Run 2 → 20
Run 3 → 30
```

This property is called:

```text
idempotency
```

The current full-refresh implementation provides simple deterministic behavior for the portfolio-sized dataset.

---

# 26. dbt Transformation Architecture

dbt manages warehouse transformations.

Current lineage:

```mermaid
flowchart LR

    RAW[PLAYERPULSE.RAW.GAMES]
    SOURCE[dbt source raw.games]
    STG[STAGING.STG_GAMES]
    MART[MARTS.FCT_PLAYER_GAMES]
    TESTS[dbt Tests]

    RAW --> SOURCE
    SOURCE --> STG
    STG --> MART
    STG --> TESTS
    MART --> TESTS
```

---

# 27. dbt Source Layer

The existing Snowflake object is declared as:

```text
source('raw', 'games')
```

This tells dbt:

- the data already exists outside dbt;
- downstream models depend on it;
- the source should appear in lineage.

This is preferable to repeatedly hard-coding:

```text
PLAYERPULSE.RAW.GAMES
```

inside every model.

---

# 28. STAGING Layer

The staging model is:

```text
STAGING.STG_GAMES
```

Its primary responsibilities are:

- extracting JSON fields;
- applying data types;
- standardizing names;
- performing lightweight cleaning;
- exposing stable source-level columns.

Typical fields include:

```text
game_id
game_url
end_time_utc
time_control
time_class
white_username
white_rating
white_result
black_username
black_rating
black_result
```

The staging layer should generally remain close to the source meaning.

---

# 29. MARTS Layer

The primary current mart is:

```text
MARTS.FCT_PLAYER_GAMES
```

Its purpose is to make analysis easier.

The raw game has two player positions:

```text
white
black
```

But an analyst interested in a specific player usually wants:

```text
player
opponent
```

The mart therefore creates fields such as:

```text
player_username
opponent_username
player_color
player_rating
opponent_rating
player_result
opponent_result
game_outcome
rating_difference
```

This moves repeated analytical logic upstream.

---

# 30. Why MARTS Exist

Without the mart, every downstream analysis might need logic such as:

```text
IF player is white:
    use white_rating
ELSE:
    use black_rating
```

Repeated logic increases the chance that two reports calculate the same metric differently.

The mart centralizes that interpretation.

---

# 31. Data Quality Architecture

Testing occurs after transformations are built.

Current tests validate assumptions including:

```text
game_id is not null
game_id is unique
end_time_utc is not null
time_class is not null
white_username is not null
black_username is not null
player_username is valid
player_color is valid
game_outcome is valid
```

Current dbt result:

```text
PASS=19
WARN=0
ERROR=0
```

---

# 32. Pipeline Success vs Data Correctness

These are not the same concept.

A task can successfully execute SQL such as:

```sql
INSERT ...
```

while still creating incorrect data.

Therefore:

```text
Airflow task success
```

means:

```text
the process executed successfully
```

while:

```text
dbt test success
```

provides additional evidence that:

```text
the resulting data satisfies defined expectations
```

Both are necessary.

---

# 33. Docker Runtime Architecture

PlayerPulse runs Airflow through Docker Compose.

Conceptually:

```mermaid
flowchart TD

    DOCKERFILE[Dockerfile]
    IMAGE[Custom Airflow Image]

    API[Airflow API Server]
    SCHED[Scheduler]
    WORKER[Worker]
    DAGPROC[DAG Processor]
    TRIGGER[Triggerer]

    DOCKERFILE --> IMAGE
    IMAGE --> API
    IMAGE --> SCHED
    IMAGE --> WORKER
    IMAGE --> DAGPROC
    IMAGE --> TRIGGER
```

The custom image includes:

```text
Apache Airflow
dbt-snowflake
Snowflake Python connector dependencies
```

This keeps dbt inside the controlled container environment.

---

# 34. Image vs Container

A Docker image is:

```text
a reusable blueprint
```

A Docker container is:

```text
a running instance of that blueprint
```

Conceptually:

```text
Dockerfile
    ↓ build
Image
    ↓ run
Container
```

This distinction is important when debugging dependencies.

Installing a package on the host machine does not automatically install it inside the Airflow container.

---

# 35. Dependency Management

Different parts of the project currently use different dependency scopes.

Local Python dependencies include:

```text
boto3
```

The Airflow Docker image additionally installs:

```text
dbt-snowflake
```

which also brings the Snowflake connector required by the Snowflake loading script.

The intended long-term goal is to keep dependency definitions explicit and reproducible.

---

# 36. Secrets and Configuration

Secrets must remain outside version control.

Examples include:

```text
AWS credentials
Snowflake password
.env
dbt profiles.yml
```

The repository's `.gitignore` excludes these local resources.

Configuration and code should be treated separately.

Conceptually:

```text
Code
+
Runtime Configuration
+
Secrets
=
Running Application
```

---

# 37. Failure Model

Different failure types can occur at different stages.

| Stage | Example Failure |
|---|---|
| API | Network timeout |
| Python | Invalid JSON |
| Local filesystem | Missing directory |
| S3 | Permission denied |
| Snowflake | Authentication error |
| Snowflake COPY | Invalid source file |
| dbt | SQL compilation failure |
| dbt tests | Duplicate or null data |
| Airflow | Task failure |

Airflow provides the orchestration-level mechanism for surfacing these failures.

---

# 38. Retry Strategy

The Airflow DAG includes retries.

Retries are useful for temporary failures such as:

```text
network interruption
temporary API error
temporary cloud service issue
```

Retries should not hide deterministic problems such as:

```text
invalid SQL
wrong credentials
broken Python syntax
```

Those problems require correction rather than repeated execution.

---

# 39. Observability

Current observability includes:

```text
Airflow task state
Airflow logs
Snowflake query results
dbt test results
row-count validation
uniqueness validation
```

A production system would extend this with:

```text
alerts
metrics
SLAs
data freshness checks
structured logging
external monitoring
```

---

# 40. Current Architecture vs Target Architecture

## Current

```text
Local Docker Airflow
        ↓
Python
        ↓
S3
        ↓
Snowflake
        ↓
dbt
```

Credentials are provided through local configuration.

Snowflake loading uses a full refresh.

The player is partly hard-coded.

---

## Target

```text
Scheduled / Managed Orchestrator
        ↓
Parameterized Ingestion
        ↓
Partitioned S3 Raw Layer
        ↓
Incremental Snowflake Loading
        ↓
dbt Models
        ↓
Automated Tests
        ↓
CI/CD (push-based — implemented)
        ↓
CI/CD (pull-request-based — target)
        ↓
Dashboard / Analytics
```

The target architecture would also include:

```text
least-privilege Snowflake roles
short-lived cloud credentials
monitoring
alerting
source freshness
incremental state management
CI validation
```

---

# 41. Current Security Limitations

The project already avoids committing secrets, but several improvements remain.

## Snowflake role

The current development configuration uses a highly privileged role.

A more mature architecture should introduce roles such as:

```text
PLAYERPULSE_LOADER
PLAYERPULSE_TRANSFORMER
PLAYERPULSE_READER
```

with separate privileges.

---

## AWS local credentials

The local Docker environment reads AWS credentials from the host.

This works for development.

Production workloads should preferably use workload identities and temporary credentials.

---

# 42. Current Scalability Limitations

The architecture works for the current dataset, but some decisions are deliberately optimized for learning rather than scale.

Examples:

```text
full refresh Snowflake loading
small number of archives
single-player analytical mart
local Airflow deployment
```

These are known limitations rather than hidden assumptions.

---

# 43. Incremental Loading — Future Design

The most important future data engineering improvement is incremental ingestion.

Instead of:

```text
TRUNCATE
↓
reload everything
```

the system could track which archives have already been loaded.

Example:

```text
S3 files
   ↓
Compare against ingestion metadata
   ↓
Load only unseen files
   ↓
MERGE into target
```

Possible metadata:

```text
source_file
file_last_modified
loaded_at
row_count
load_status
```

---

# 44. Future Product Event Architecture

PlayerPulse is planned to expand beyond public game data.

A synthetic product-event stream could follow:

```text
Product Events
      ↓
Python Generator
      ↓
S3
      ↓
Snowflake RAW.EVENTS
      ↓
dbt STAGING
      ↓
Sessions
      ↓
Funnels
      ↓
Cohorts
      ↓
Retention
      ↓
Churn
```

This would reuse the same infrastructure while introducing product analytics concepts.

---

# 45. Template Architecture

PlayerPulse can be generalized into the following reusable pattern:

```mermaid
flowchart LR

    SOURCE[External Data Source]
    INGEST[Python Ingestion]
    RAW[Raw Object Storage]
    WAREHOUSE[Cloud Warehouse]
    STAGING[STAGING Models]
    MARTS[MART Models]
    TESTS[Data Tests]
    BI[Analytics]

    SOURCE --> INGEST
    INGEST --> RAW
    RAW --> WAREHOUSE
    WAREHOUSE --> STAGING
    STAGING --> MARTS
    MARTS --> TESTS
    MARTS --> BI
```

---

# 46. What Changes Between Projects?

The reusable infrastructure can stay similar.

The source-specific logic changes.

For another API project:

```text
Keep:
Airflow
Docker
S3 pattern
Snowflake structure
dbt structure
testing pattern
Git workflow

Replace:
API client
source-specific fields
raw table definitions
staging model
business marts
business tests
```

This is why PlayerPulse can serve as a personal data engineering template.

---

# 47. Architectural Principles

PlayerPulse follows several principles.

## Preserve raw source data

Do not destroy the original representation too early.

## Separate responsibilities

Use each tool for the problem it solves best.

Applied to CI/CD itself in sections 49–50: test validation and deployment are
separate workflows, not one.

## Make pipelines rerunnable

Repeated execution should not silently corrupt data.

## Test data, not only code

Successful execution does not guarantee correct output.

## Keep secrets outside Git

Configuration and credentials must be separated from source code.

## Prefer reproducibility

Another environment should be able to recreate the platform.

## Start simple

Do not introduce distributed-system complexity before the scale requires it.

## Document limitations

A portfolio project is more credible when its limitations are explicit.

## Databricks pipeline

The same separation-of-responsibilities principle extends to the Databricks pipeline (sections
51-60): Bronze/Silver/Gold hold the same roles as RAW/STAGING/MARTS, proving the principle is
architectural, not tool-specific.

---

# 48. Architecture Summary

The current end-to-end architecture is:

```text
Chess.com Public API
        ↓
Python ingestion
        ↓
Raw JSON files
        ↓
Apache Airflow orchestration
        ↓
AWS S3
        ↓
Snowflake Storage Integration
        ↓
Snowflake RAW
        ↓
dbt STAGING
        ↓
dbt MARTS
        ↓
dbt data quality tests
        ↓
Analytics-ready data
       ↓
GitHub Actions validates and redeploys on every future change
```

The most important architectural lesson from PlayerPulse is not any individual technology.

It is understanding the separation between:

```text
ingestion
orchestration
storage
compute
transformation
testing
security
analytics
```

and how those layers work together as one data platform.

A parallel Databricks/Delta Lake pipeline (sections 51-60) reimplements the same layering on a
second engine, demonstrating that the pattern — not any single vendor — is the actual architecture.

---

# 49. CI/CD Architecture

PlayerPulse runs two chained GitHub Actions workflows.

```mermaid
flowchart TD

    PUSH[Push to main]
    TESTWF[dbt-tests.yml]
    TEST[job: test]
    DBTTEST[dbt test]

    DEPLOYWF[dbt-deploy.yml]
    DEPLOY[job: deploy]
    DBTBUILD[dbt build]

    PUSH --> TESTWF
    TESTWF --> TEST
    TEST --> DBTTEST
    DBTTEST -- success --> DEPLOYWF
    DEPLOYWF --> DEPLOY
    DEPLOY --> DBTBUILD
```

The two workflows communicate through `workflow_run`, not through `needs:`.

`needs:` links jobs inside the same file. `workflow_run` links entire separate workflow files —
one workflow triggers when another workflow finishes, and can inspect whether it succeeded before
proceeding.

Conceptually:

```text
needs:         same file, job-to-job
workflow_run:  different files, workflow-to-workflow
```

## Why deploy checks conclusion, not just completion

`dbt-deploy.yml` does not simply trigger when `dbt-tests.yml` finishes — it checks
`github.event.workflow_run.conclusion == 'success'` before running anything. A completed workflow
is not the same as a successful one. This mirrors the distinction already established between
pipeline execution and data correctness.

## Secrets in this context

Both workflows independently read the same three GitHub repository secrets and independently
generate their own `~/.dbt/profiles.yml`, scoped to the runner's lifetime. Neither workflow persists
credentials, and neither reads the other's generated profile — each run starts from nothing and
rebuilds what it needs.

---

# 50. Why Two Workflow Files Instead of One

A single file with two jobs, connected by `needs: test`, would accomplish the same outcome with
less configuration.

This project uses two separate files instead, deliberately.

## The trade-off

```text
One file, two jobs:
  Simpler to read
  Dependency is explicit and local
  Test and deploy logic live in the same place

Two files, workflow_run:
  Test and deploy are independently modifiable
  A change to deploy logic cannot accidentally affect test logic in the same diff
  The dependency is less visible, harder to trace at a glance
```

## Why this project chose separation anyway

This is the same principle from section 5 — *give each tool, or in this case each workflow, one
responsibility — applied to CI/CD itself rather than to data infrastructure. `dbt-tests.yml` owns
validation. `dbt-deploy.yml` owns deployment. Neither file needs to understand the other's internal
steps, only whether the other succeeded.

The cost is real: tracing *why* a deployment did not run requires checking a different file than
the one that ran the tests. For a project this size, either approach is defensible — the choice
here favors architectural clarity over configuration simplicity.

---

# 51. Databricks Delta Lake Extension — Overview

PlayerPulse runs a second, parallel ingestion path on Databricks, using Delta Lake and Unity
Catalog against the same raw S3 data the Snowflake pipeline consumes. It is not a replacement.
It is proof that the RAW → STAGING → MARTS layering is an architectural pattern, not something
tied to Snowflake's syntax — the same thinking, renamed Bronze/Silver/Gold as is conventional on
Databricks, running on a completely different engine.

```mermaid
flowchart TD
    S3[S3: chesscom/games/ raw JSON]
    EL["Unity Catalog External Location<br/>playerpulse_s3_raw (read-only)"]
    BRONZE["Bronze: bronze.games_raw<br/>managed Delta table"]
    SILVER["Silver: silver.games<br/>managed Delta table"]
    GOLD["Gold: gold.fct_player_games<br/>managed Delta table"]

    S3 --> EL
    EL --> BRONZE
    BRONZE -->|LATERAL VIEW EXPLODE| SILVER
    SILVER -->|player perspective| GOLD
```

Both pipelines read the exact same S3 source. Neither writes back to it. They are two independent
consumers of one raw data lake, which is itself a real-world pattern — one team's warehouse and
another team's lakehouse can both sit downstream of the same object storage without conflict.

---

# 52. Unity Catalog Namespace and Access Model

Unity Catalog organizes data in three levels: `catalog.schema.table`. `workspace` is the catalog,
`bronze`/`silver`/`gold` are schemas, and `games_raw`/`games`/`fct_player_games` are the tables.
This is the same three-level idea as Snowflake's `database.schema.table` — a different vendor's
name for an identical structure.

## Storage Credential and External Location

Two separate objects grant Databricks access to S3, mirroring Snowflake's Storage Integration:

```text
Storage Credential   → the AWS IAM role Databricks assumes (playerpulse-databricks-s3-cred)
External Location    → the specific S3 path that credential is allowed to touch
                        (playerpulse_s3_raw)
```

A Storage Credential alone grants nothing — it is a set of AWS-side permissions with no path
attached. An External Location is what actually authorizes reading a specific S3 location, using
that credential.

## The AWS trust chain

`PlayerPulseDatabricksS3Read`'s trust policy has two required principals, not one:

```text
1. Unity Catalog's own static AWS principal
   arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL
2. The role itself (a self-assuming role)
```

Databricks assumes the role through its own central account first, then that assumed identity has
to assume the same role again on behalf of the workspace — hence the role must trust itself. Both
assumptions are further gated by an External ID condition, the same confused-deputy protection
already used for the Snowflake integration: without the correct External ID, even the right
principal cannot assume the role.

## Why the External Location is scoped to the whole bucket, not to `chesscom/`

The Snowflake Storage Integration is scoped tightly to `s3://.../chesscom/` — nothing outside that
prefix is reachable. The Databricks equivalent could not be scoped the same way: Databricks'
"Create external location" quickstart form validates its input as a bare bucket name and rejects
any trailing path, so `s3://bucket/chesscom/` fails validation outright.

The External Location is therefore created at the bucket root. This does not widen access in
practice — the IAM role's own inline policy already grants `GetObject`/`ListBucket` on the whole
bucket, not just the `chesscom/` prefix, so the External Location's scope matches what the IAM
role already allowed. The prefix filtering that Snowflake enforces at the integration level happens
here at the query level instead — the notebook only ever reads `chesscom/games/...` paths, even
though Unity Catalog would technically permit reading elsewhere in the bucket.

---

# 53. Managed vs. External Tables

Unity Catalog draws a line between tables it owns and tables it does not, and this project hit
that line directly while building it.

Creating a schema with its storage location pointed at the read-only `playerpulse_s3_raw` External
Location failed immediately: *"Creating a schema with a read-only storage location is not
supported."* A managed table needs to write its own Parquet/Delta files somewhere. A read-only
credential cannot satisfy that, by definition.

```text
Managed table    → Databricks owns the storage, in the metastore root
                    (no custom storage location set on the schema)
External table   → storage lives somewhere the user owns (here, S3),
                    accessed only through a Storage Credential
```

Bronze, Silver, and Gold are all managed tables with no custom schema storage location — Databricks
owns their files, exactly as Snowflake owns STAGING and MARTS. `playerpulse_s3_raw` is used for
exactly one purpose: granting read access to the raw S3 path inside the notebook code
(`spark.read...`). It was never meant to back a schema's storage, and Unity Catalog's refusal to
let it do so is correct, not a bug.

---

# 54. Bronze Layer

```python
raw_path = "s3://playerpulse-ali-jazz-raw-2026-218484443553-ca-central-1-an/chesscom/games/"
df_bronze = spark.read.option("multiLine", "true").format("json").load(raw_path)
```

Each raw file was written by `fetch_player_games.py` with `json.dumps(data, indent=2, ...)` — one
pretty-printed, multi-line JSON object per file, not one-record-per-line (NDJSON), which is Spark's
default assumption for JSON. `multiLine` tells Spark to parse each file as a single JSON document
instead of expecting a record boundary at every newline.

The S3 keys are partitioned as `chesscom/games/username=.../year=.../month=.../games.json`.
Pointing the reader at the parent folder rather than a specific file triggers Spark's partition
discovery: `username`, `year`, and `month` are inferred directly from the folder names and added
as columns, with no explicit schema needed.

The result is one row per source file, each holding a `games` array with every game from that
player/month untouched — the same role RAW plays in the Snowflake pipeline: preserve what was
ingested, exactly as it arrived, before any interpretation happens. An `ingested_at` timestamp
(`current_timestamp()`) is added before writing to `bronze.games_raw`, giving Bronze slightly finer
lineage than Snowflake RAW's single `loaded_at` per batch.

---

# 55. Silver Layer

## LATERAL VIEW EXPLODE

Bronze holds one row per file, with a `games` column that is an array. Silver needs one row per
game. `LATERAL VIEW EXPLODE` is Spark SQL's mechanism for exactly this: it takes an array-valued
column and produces one output row per array element, repeating every other column across each new
row. This is the same operation Snowflake's `LATERAL FLATTEN` performs on a VARIANT array — same
concept, different SQL dialect:

```sql
-- Snowflake
select ... from raw_table, lateral flatten(input => games_column)

-- Spark SQL
select ... from bronze_games
lateral view explode(games) exploded_table as game
```

## Flattening the nested structs

Once exploded, each row's `game` value is a struct with nested sub-structs (`white`, `black`,
`accuracies`). Spark's dot notation (`game.white.username`) reaches into them directly, the same
way Snowflake's `:` path syntax (`game_payload:"white":"username"`) reaches into a VARIANT — the
field mapping is a line-by-line port of the dbt `stg_games` model. `end_time`, a Unix epoch integer,
is converted with `timestamp_seconds()`, Spark's equivalent of Snowflake's `to_timestamp_ntz`.

`silver.games` keeps `source_username`, `source_year`, `source_month`, and `ingested_at` from
Bronze — carrying forward structured lineage columns instead of a single flat `source_file` string,
which is a small improvement over the Snowflake staging model, made possible only because Bronze's
partition discovery already produced structured columns instead of a filename to parse.

---

# 56. Gold Layer

Gold's job is reframing, not just cleaning. Every Silver row is symmetric — it has a `white_*` side
and a `black_*` side, and nothing in the row says which one is "Ali." Gold answers that question
with a `CASE WHEN lower(white_username) = 'ajaza'` check, repeated once per pair of columns
(username, rating, result, accuracy), to derive `player_*`/`opponent_*` columns instead — a direct
port of the dbt `fct_player_games` mart, same logic, same output shape.

## Why this needs two passes

`game_outcome` and `rating_difference` both depend on columns the reframing step just created
(`player_result`, `opponent_result`, `player_rating`, `opponent_rating`). SQL evaluates all
expressions in a single `SELECT` against the *input* row, so a column defined earlier in that same
`SELECT` cannot be referenced by another expression in it. A second pass — here, a second CTE reading
from the first — is required once a computed value needs to feed a further computation.

`game_outcome`'s fallback logic is deliberate, not an oversight: chess.com's `result` field is never
literally `'draw'` — a draw shows as `'agreed'`, `'repetition'`, `'stalemate'`, `'insufficient'`, or
similar on both sides. Checking only for `player_result = 'win'` and `opponent_result = 'win'`, and
falling through to `'draw'` when neither is true, correctly classifies every draw variant without
needing to enumerate them.

---

# 57. What Delta Lake Actually Is

Delta Lake is not a database and not a warehouse. It is a storage **format** — Parquet files plus a
transaction log — that adds guarantees plain Parquet does not have on its own:

```text
ACID transactions   → a write either fully succeeds or fully fails, never half-applied
Schema enforcement  → a write with the wrong schema is rejected, not silently accepted
Time travel         → older versions of a table can be queried or restored
Unified batch/stream → the same table can be read as a static snapshot or a stream
```

Every `CREATE TABLE`/`CREATE OR REPLACE TABLE` in this project's Bronze/Silver/Gold layers is,
underneath, writing Parquet files plus a Delta transaction log — the `format("delta")` on Bronze's
write call is what requests that log. Databricks itself is a compute and governance platform (the
notebooks, Unity Catalog, cluster/serverless compute); Delta Lake is what turns the S3/metastore
storage those tables sit on into something with warehouse-like guarantees. The combination —
cheap object storage plus a transactional layer on top — is what "lakehouse" refers to. Snowflake
reaches similar guarantees differently: storage and the transactional guarantees are bundled
together as one proprietary system, not a separate open format over generic object storage.

---

# 58. Data Quality Checks on Databricks

Six checks, written as direct SQL assertions rather than through a testing framework:

```text
not_null        → game_id, player_username, opponent_username
unique          → game_id
accepted_values → game_outcome IN ('win','loss','draw')
                   player_color IN ('white','black')
custom          → Silver ajaza-filtered row count == Gold row count
```

Every dbt generic test compiles down to exactly this shape: a SQL query that must return zero rows
to pass. Writing them by hand here makes that mechanism visible instead of hidden behind dbt's
macros. The custom check is the only one with no dbt equivalent among the four generic tests — it
exists specifically to catch a reframing bug (Gold's `WHERE` clause silently dropping or duplicating
rows), the same category of risk the project's weekly self-study plan calls out as worth a
hand-written test rather than a boilerplate one.

---

# 59. Comparison — Snowflake/dbt vs. Databricks/Delta Lake

| Concept | Snowflake / dbt | Databricks / Delta Lake |
|---|---|---|
| Raw layer | RAW (VARIANT column) | Bronze (managed Delta table) |
| Cleaned layer | STAGING | Silver |
| Business layer | MARTS | Gold |
| Array/nested expansion | `LATERAL FLATTEN` | `LATERAL VIEW EXPLODE` |
| Nested field access | `payload:"field"` | `struct.field` |
| Cloud storage grant | Storage Integration + External Stage | Storage Credential + External Location |
| Trust mechanism | AssumeRole + External ID | Self-assuming role + Unity Catalog principal + External ID |
| Full-refresh write | `dbt build` (table materialization) | `CREATE OR REPLACE TABLE ... AS` |
| Row-level test | dbt generic test (`not_null`, `unique`, ...) | Hand-written SQL assertion |
| Elevated dev role | `ACCOUNTADMIN` | N/A — role was read-only from the start |

The point of this table is not that one platform is better. It is that the same five ideas —
preserve raw data, separate cleaning from business logic, expand nested data explicitly, grant
narrow scoped access, test with queries that must return nothing — show up under different names
on both platforms. Learning the pattern transfers; memorizing one vendor's syntax does not.

---

# 60. Current Limitations of the Databricks Extension

```text
Manual execution      → runs cell by cell in a notebook, no scheduler
No orchestration      → not triggered by Airflow or Databricks Jobs
No CI coverage        → GitHub Actions validates the dbt pipeline only, not this notebook
Bucket-root scope     → External Location covers the whole bucket, not just chesscom/
                         (see section 52 for why, and why it does not widen real access)
Free Edition          → serverless-only compute, single workspace, no cluster-level tuning
Small dataset         → same 10-game dataset as the rest of the project; no volume/performance
                         testing has been done on this path
```

---
---
