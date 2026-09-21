# DSW versions

Each official DSW minor version has a separate `sync/vX.Y` translation branch.
The daily workflow discovers versions on official Weblate and creates a branch once
the matching official Git source catalogs are available.

An open official project is `active`; a locked one is `maintenance`.
Neither state archives or deletes a local branch. Versions temporarily absent from the
official listing are retained. Old versions can still be reviewed locally; Weblate itself
decides whether it accepts uploads to a locked project.

There is no separate local locale release number. Source commits are recorded in
`upstream/upstream.lock.yml`, and translation changes are tracked by Git commits.
