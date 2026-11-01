# PlayerPulse CI/CD — architecture, safeguards, evidence

## Architecture

```
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
            protected GitHub environment + reviewer approval
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
- Do not promise rollback of `dbt build` or a transactionally safe release until you have tested an actual recovery procedure.

## Release gate — configure later, not before Monday

1. In repo Settings -> Environments, create `snowflake-production` with required reviewers and branch restrictions to `main`.
2. Store `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, and `SNOWFLAKE_PASSWORD` as **environment secrets**, never hardcode them.
3. Store `SNOWFLAKE_ROLE`, `SNOWFLAKE_DATABASE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_SCHEMA` as protected environment variables. E.g. `SNOWFLAKE_DATABASE=PLAYERPULSE`, `SNOWFLAKE_SCHEMA=ANALYTICS`. Role should be restricted to required read/write paths (not ACCOUNTADMIN).
4. Verify the Snowflake role cannot write `RAW` or arbitrary databases and has only the needed privileges on materialization schemas.
5. Prove a staging `dbt build` works first in a dedicated, disposable CI schema under separate credentials. Confirm output table names and warehouse cost.
6. Only if steps 1-5 have passed, set repository variable `ENABLE_SNOWFLAKE_DEPLOY` to `true`. Re-run after manual approval. Never enable this before reviewing the current repository main branch configuration.

## Evidence for Mujin (fill after actual GitHub verification)

| Evidence | URL / observation | Verified? |
|---|---|---|
| Pull Request | TBD | No |
| Green Python tests + lint | TBD | No |
| Green offline dbt parse | TBD | No |
| Deliberately failing assertion run | TBD | No |
| Fixed assertion run | TBD | No |
| CD skip for PR | TBD | No |
| CD disabled by default (`ENABLE_SNOWFLAKE_DEPLOY` unset) | Configured in proposal; runner pending | No |
| Actual Snowflake deployment | Not performed | No |

## Suggested short explanation in an interview

> I revised a dbt + Snowflake project to run Python unit tests, linting and an offline dbt parse check for each pull request. The CI jobs have read-only repository permissions and no cloud credentials. Delivery is separately gated on the successful push-to-main CI, matches the tested commit SHA, and remains disabled until a protected Snowflake environment with restricted access is approved. Database integration tests and production rollout are explicitly tracked as follow-up work.

Only use this explanation after the stated CI checks pass on GitHub.
