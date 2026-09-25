# Product Identity

The final product name is **MasterBrain**. The GitHub repository is
[`jbone3311/MasterBrain`](https://github.com/jbone3311/MasterBrain). It was renamed
from `jbone3311/CW-EmailBrain` on 2026-09-25. The rename did not change commits,
the `main` branch, release status, or the FileOS donor. Update local Git remotes,
automation settings, and bookmarks that still use the old address; historical
references remain meaningful. See [the consolidation receipt](REPOSITORY_CONSOLIDATION.md).

`email_brain`, `email-brain`, EmailBrain and Email Brain are compatibility/internal
names for the Email source capability. They may remain in imports, commands, database
settings, migrations and historical documents where changing them would create risk.
New user-facing product material uses MasterBrain.

FOS-Master is the donor and current operational FileOS reference. It is not an alias
for MasterBrain, has not been replaced, and must not be renamed or retired before the
parity and cutover gates in [FOS_MIGRATION.md](FOS_MIGRATION.md).

The machine-readable identity is in [`MANIFEST.json`](../MANIFEST.json). The Python
distribution and preferred command are `masterbrain`; `email-brain` remains a
compatibility command during migration.
