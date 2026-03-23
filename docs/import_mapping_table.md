# Legacy Import Mapping

| File entity | Canonical DB entity |
| --- | --- |
| `workspace_metadata.json` | `workspaces.metadata_json`, `artifacts(workspace_metadata)` |
| `model/model_version.json` | `workspaces.active_model_version`, `workspace_versions` |
| `model/case_model.json::claims[]` | `claims`, `claim_versions` |
| `model/case_model.json::relations[]` | `claim_relations` |
| `state/version_changelog.json::events[]` | `governance_events` |
| Any JSON/text file under workspace root | `artifacts` |

Unsupported or unreadable files are reported as partial failures and do not abort the whole import.
