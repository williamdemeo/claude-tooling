# Transcript retention

Session transcripts live under `~/.claude/projects/<encoded-cwd>/` as `.jsonl` files,
one per session.  Claude Code prunes them after `cleanupPeriodDays` (default 30).

**Chosen setting (verified in `~/.claude/settings.json`, 2026-08-09)**:

    "cleanupPeriodDays": 3650

i.e. ~10 years; transcripts are deliberately kept.  They are the raw material for the
planned "skill extractor" project (mining past sessions for skills, e.g. for
williamdemeo.github.io, whose skills are yet to be written).
