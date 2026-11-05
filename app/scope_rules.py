"""Which epics still belong in the prioritization matrix. Pure rules, no team ids, no I/O.

The matrix is a forward-planning tool: once an epic is In Dev or downstream (Deployed, Waiting To
Accept, Closed) it is committed work, not a prioritization decision. Team ids live in config.
"""

# statusCategory values that mean "no longer a prioritization decision"
OUT_OF_SCOPE_CATEGORIES = {"in progress", "done", "complete"}

# status names that are In Dev or downstream of it, matched case-insensitively
DOWNSTREAM_STATUSES = {
    "in dev", "in development", "development", "in progress",
    "in test", "in testing", "in qa", "qa", "code review", "in review",
    "ready for deploy", "deploying", "deployed",
    "ready to accept", "waiting to accept", "accepted",
    "released", "resolved", "done", "closed", "cancelled", "canceled",
}

# statuses that remain prioritizable (informational)
IN_SCOPE_STATUSES = {"parking lot", "funnel", "analysis", "backlog", "on hold"}


def in_scope(status_name="", status_category=""):
    if (status_category or "").strip().lower() in OUT_OF_SCOPE_CATEGORIES:
        return False
    if (status_name or "").strip().lower() in DOWNSTREAM_STATUSES:
        return False
    return True


def out_of_scope_reason(status_name="", status_category=""):
    """Short reason an epic is excluded, or None if in scope."""
    s, c = (status_name or "").strip(), (status_category or "").strip()
    if c.lower() == "done" or s.lower() in {"closed", "done", "cancelled", "canceled", "resolved"}:
        return f"closed ({s or c})"
    if not in_scope(s, c):
        return f"in flight ({s or c})"
    return None
