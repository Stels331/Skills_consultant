# Legacy File-Primary Exit Checklist

- All new workspace creation paths use canonical DB as the first write.
- Importer has migrated the required legacy workspace set.
- Drift alarms are monitored and empty for the agreed observation window.
- File consumers read materialized exports only and no longer persist primary state directly.
- Rollback runbook has been rehearsed against the current migration head.
