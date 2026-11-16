---
id: cleanup-orphans
files: [wardrobe/**]
effort: low
sandbox: full
network: false
timeout: 15
---
Run an existing maintenance script. Write no code. Change no source file.

## What to run

From the `wardrobe/` directory, using that project's virtualenv interpreter:

    cd wardrobe
    venv\Scripts\python.exe cleanup_orphans.py --apply

`cleanup_orphans.py` already exists and is complete — read it before running so
you know what it does, but **do not modify it**. It deletes item rows whose
image file is missing from storage, plus three accounts created by seed and
test runs. It copies `wardrobe.db` into `wardrobe/backups/<timestamp>-cleanup/`
before deleting anything, so no extra backup is needed.

## Why

31 of 44 item rows point at image files that were never created, by seed
scripts and by the test suite running against the real database. Both the web
closet and the Android app render them as blank "Image unavailable" cards.

## Expected result

Before the run: 6 users, 44 items, 31 with no file on disk.
After the run: 3 users remain, and **every** remaining item has a file on disk.

The script prints an "after" table. In your summary, quote that table verbatim,
and state the exact counts of item rows and accounts deleted.

## Stop and report instead of improvising if

- The script reports a different number of orphans than 31, or a different set
  of accounts than `admin@exmple.com`, `alice_…` and `public_tester_…`.
- Any remaining item still shows `missing=` greater than 0 afterwards.
- The run raises an exception.

In any of those cases, do not re-run it, do not edit the script, and do not try
to fix the data by hand. Report what happened.

## Done when

The script has run once with `--apply` and its "after" table shows
`missing=0` for every remaining user. No file in `wardrobe/` has been edited.
