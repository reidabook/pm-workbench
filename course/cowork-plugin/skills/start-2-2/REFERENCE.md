# 2.2 Reference: signals and evidence

## Evidence types and default points
| Type | Points |
|---|---|
| Usage data / analytics | 2.0 |
| Customer / user feedback | 1.5 |
| Prospective customer feedback | 1.0 |
| Support tickets / defects | 1.0 |
| Competitor does it | 0.5 |
| Internal ask | 0.5 |

Validation score: 1 with no evidence; + points per distinct type; +0.25 per repeat (max +0.5); ceiling 5;
competitor-only capped at 1.5. Override per epic in the drawer. Weights are editable on Settings.

## Flow
source → ideas (extract or by hand) → objective (assign themes) → group → Generate PRD / Draft epic.
Evidence follows the work: idea → group → draft → Jira epic (an `h3. Validation` block in the description) and
into the bundle handed to `/pm-generate-prd`.
