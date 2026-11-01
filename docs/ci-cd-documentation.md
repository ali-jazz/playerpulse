# PlayerPulse CI/CD — architecture, safeguards, evidence

## Architecture

```text
PR targeting main / push main
            |
            v
    [dbt tests workflow]
       /            \
      v              v
Python unit/lint     dbt parse (fake profile; NO Snowflake)
      \              /
       \            /
      CI status: passed or failed
             |
             +--> PR: review and merge only if green
             |
             +--> push main: workflow_run completed
                         |
          gate: CI=success AND event=push AND branch=main
                AND same repository AND ENABLE_SNOWFLAKE_DEPLOY=true
                         |
            Production environment protections (required before CD enablement)
                         |
                    checkout tested SHA
                         |
              dbt build -> Snowflake (ONLY when safely enabled)
```

## Why the controls exist

- Pull request jobs use `contents: read`, no Snowflake/AWS secrets, and no privileged `pull_request_target` trigger.
- SHA-pinned actions reduce drift in the action implementation. `checkout.ref` in CD uses the SHA from the successful CI workflow run; they are two different SHA concepts.
- The deploy job is disabled when the repository variable does not equal the string `true`. Jobs on PR-completed runs should be skipped. A skipped deploy job is **not** an actual CD run.
- Environment protections are configured in GitHub Settings, not guaranteed by YAML alone. Explicit reviewer approval is needed before granting CD environment secrets.
- `target: prod` with dbt `generate_schema_name_for_env` preserves custom `STAGING` and `MARTS` production names. The CI target uses an isolated schema instead; this macro has to be adopted with care for any other consumers.
- `dbt parse` checks compilation/parsing logic without connecting to Snowflake; it does not establish that SQL executes or data quality holds in the warehouse.
- Rollback procedures have not yet been implemented or validated.

## Release gate — configure before enabling production CD

1. In repo Settings -> Environments, create `snowflake-production` with required reviewers and branch restrictions to `main`.
2. Store `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, and `SNOWFLAKE_PASSWORD` as **environment secrets**, never hardcode them.
3. Store `SNOWFLAKE_ROLE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_SCHEMA` as protected environment variables. E.g. `SNOWFLAKE_DATABASE=PLAYERPULSE`, `SNOWFLAKE_SCHEMA=ANALYTICS`. Role should be restricted to required read/write paths (not ACCOUNTADMIN).
4. Verify the Snowflake role cannot write `RAW` or arbitrary databases and has only the needed privileges on materialization schemas.
5. Prove a staging `dbt build` works first in a dedicated, disposable CI schema under separate credentials. Confirm output table names and warehouse cost.
6. Only if steps 1-5 have passed, set repository variable `ENABLE_SNOWFLAKE_DEPLOY` to `true`. Never enable this before reviewing the current repository main branch configuration.

## Verified GitHub Actions evidence — 2026-11-01

The evidence below was inspected in GitHub Actions for [Pull Request #1](https://github.com/ali-jazz/playerpulse/pull/1), from `cicd` into `main`. The PR was open and unmerged when this documentation was prepared.

| Check | Evidence | Outcome |
|---|---|---|
| Pull Request | [PR #1](https://github.com/ali-jazz/playerpulse/pull/1) | Open; merge not performed at verification time |
| Initial CI | [Successful workflow run](https://github.com/ali-jazz/playerpulse/actions/runs/41338961397) | Python checks and offline dbt parse passed |
| Intentional regression | [Failed workflow run](https://github.com/ali-jazz/playerpulse/actions/runs/41339578168) | `Run unit tests` failed in the Python job, while dbt parse passed |
| Recovery after correction | [Successful workflow run](https://github.com/ali-jazz/playerpulse/actions/runs/41339689252) | Python tests, Ruff, and offline dbt parse passed |
| Last verified application commit | `b2358b6976a3440eab5530be8f9db99085a9406b` | Both CI jobs successful at this revision |
| PR-triggered privileged deployment | CD workflow checks event `push`, branch `main`, successful CI, same repository and explicit enablement flag | Design reviewed; no live negative-test of privileged deployment performed |
| Legacy CD workflow | Disabled manually in GitHub Actions, Legacy deployment workflow manually disabled | Operational safeguard; verify again before merging |
| Production Snowflake deployment | Not attempted | Not verified |

### Interpretation and limits

- The red-to-green sequence demonstrates that a failing unit test makes the CI run fail, and that correcting it restores a green CI run. **It does not prove GitHub branch protection blocks merging**. That requires separately configured and verified required status checks.
- The new `deploy.yml` checks `workflow_run.event == 'push'`, `head_branch == 'main'`, successful CI, matching source repository and `ENABLE_SNOWFLAKE_DEPLOY == 'true'`. It is designed not to deploy after a PR CI run. The original deployment workflow on `main` has been manually disabled; that is important until the guarded workflow reaches `main`.
- The CD gate and environment name are defined in YAML, but environment approval rules, Snowflake least-privilege credentials and integration validation have **not** been confirmed. No production rollout has been exercised.
- The passing `dbt parse` uses placeholder values and does **not** connect to Snowflake, execute SQL models, or validate warehouse data.
- Documentation-only commits can trigger a new PR CI run. Recheck the latest run and PR merge state before merging.


The linked CI checks passed. The CD safeguards are configured but have not been exercised in production.