# Hosted collection accounts

The Pi service uses hosted identity isolation as of 2026-09-18. Preserve this
configuration during every future release. The Windows app remains local and
single-user.

- Service: `pokemon-collection.service`, bound to `127.0.0.1:8766`.
- Application: `/home/ealtenho/pokemon-collection`.
- Hosted environment: `/etc/systemd/system/pokemon-collection.service.d/tenant.conf`.
- Each verified, normalized email selects `user_data/users/<sha256-email>/`.
- Inventory, locations, history, decks, assignments, imports, and OCR evidence
  are scoped to that account. Only the reference catalog is shared.
- The original top-level SQLite files are retained migration snapshots; they
  are no longer the live saves. Never replace tenant data with those snapshots.
- `deploy/backup.py` backs up the original databases and every tenant's inventory
  and decks, preserving their relative paths and verifying SQLite integrity.
  The existing daily backup timer runs this script.

To invite someone, create an exact-email Allow policy and attach it only to the
Pokemon Collection application (`cards.altylab.com`). Do not expand the reusable
owner-only policy, which protects other applications. New users start empty;
they can request a one-time login code sent to their approved email address.

Migration backups and verification evidence are retained on the Pi under
`/home/ealtenho/pokemon-collection-releases/tenant-20260918/`. The full archive
`before-migration.tar.gz` and `migration-manifest.json` capture the original
data. Restoration must preserve newer per-user saves. Do not restore the old
single-user backend or disable hosted mode while additional users are allowed
through Cloudflare Access: that would expose the shared owner save. Stop the
service during recovery and restore a version that retains authentication and
tenant scoping.

Validation: 134 tests passed against the staged Pi release, including real
RS256 verification with disposable keys, invalid-token rejection, concurrent
request identity separation, private storage, and all-tenant backups. Owner
sign-in and the migrated collection were verified through the public website.
New users must complete their own first login; their credentials are not used
by deployment checks.
