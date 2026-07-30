# PlayerPulse

PlayerPulse is an end-to-end cloud data engineering and product analytics project built to process player activity and event data.

## Planned Architecture

```text
Public API and simulated events
            |
            v
        Python ingestion
            |
            v
          AWS S3
            |
            v
        Snowflake RAW
            |
            v
     dbt transformations
            |
            v
Engagement, retention and churn marts
