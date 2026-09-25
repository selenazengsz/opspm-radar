# OpsPM Tracker

An independent Operations and Product Management opportunity radar with transparent sponsorship evidence and browser-local application tracking.

```bash
npm run dev
```

The production page is `/`. The design archive remains available at:

- `/design/a/` — Radar Timeline
- `/design/b/` — Evidence Desk
- `/design/c/` — Opportunity Board

## Data model

- Public roles are normalized from Summer 2027 Role Index, New Grad Jobs 2027, ApplyGuy's frequently reverified 2027 internship feed, and strict early-career subsets of Jobright's Product Management and Business Analyst New Grad feeds.
- Company-level H-1B history comes from a compact index derived from the USCIS Employer Data Hub.
- “H-1B history” is evidence of past approvals, not a promise for a specific role.
- Under the default eligibility rule, a role remains visible unless a source explicitly reports no sponsorship or a citizenship restriction.
- Saved roles, statuses, and notes stay in IndexedDB in the current browser and are never included in the public build.

## Refresh and build

```bash
python3 scripts/refresh_jobs.py
PYTHONPATH=scripts python3 -m unittest scripts/test_refresh_jobs.py
python3 scripts/build_site.py
```

GitHub Actions refreshes the public feed daily and deploys only `dist/`, excluding `.personal-workbench/` and other local files.
