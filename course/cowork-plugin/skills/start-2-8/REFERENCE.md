# 2.8 Reference: scoring

`Score = (w_sv·SV + w_ui·UI + w_urg·Urg + w_theme·Theme + w_conf·Conf + w_val·Validation) / Effort`
- Defaults: SV .30, UI .25, Urg .15, Theme .15, Conf .15, Validation 0. Effort S=1, M=2, L=3.
- ThemeScore = 5 − 4·(rank − 1)/(max − 1).
- Rank: score descending, ties share the lowest rank. Bands by rank quantile: P1 15%, P2 40%, P3 70%, P4 rest.
- Parked rows are excluded and pinned; Raise-to-P1 forces P1.
- Confidence gap: confidence ≤ threshold (default 2) on a P1/P2.

## Push to Jira
Dry run lists priority changes (computed ≠ Jira) and the rank order; *Apply* writes priorities and ranks
(Jira Agile rank API). Untick changes to skip them.

## Export
*Export spreadsheet* writes a values-only `.xlsx` of the matrix.
