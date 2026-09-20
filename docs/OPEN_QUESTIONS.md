# Owner decision parking lot

No reply is required to continue synthetic development. Defaults below are bounded
engineering assumptions, not permission to connect accounts, spend money, retain
mail forever, share it with others, or disclose it to remote models.

| ID | Decision to revisit | Safe working assumption | Blocks |
|---|---|---|---|
| Q01 | First provider/account and historical backfill window | Fastmail JMAP protocol first; synthetic mail only | Live sync enrollment |
| Q02 | AWS/Supabase/Neon, region, existing cloud operations, monthly ceiling | AWS target design; portable Postgres; spend nothing | Cloud provisioning |
| Q03 | One private owner or household/team at launch? | Owner-only access per tenant; no sharing | Invitations/member grants |
| Q04 | Retention for raw mail, attachments, facts, logs, backups | No production ingestion until policy selected | Production ingestion/purge |
| Q05 | Allowed remote model providers, content classes, region, budget | Remote inference disabled | Any remote mail disclosure |
| Q06 | Local inference hardware and always-on device | Code/FTS remain functional without it | Model selection/capacity |
| Q07 | Folder/label naming and protected senders/classes | Canonical roles; no provider writes | Organization rollout |
| Q08 | Dropbox source checkout versus Factory's code/content separation | Source requested beside Dropbox Factory; live state elsewhere | Formal Factory layout/bind |
| Q09 | Which Products may receive attachment exports? | None automatically; export proposals only | Cross-Product delivery |
| Q10 | Raw download/attachment rendering permissions | Bounded extracted text only; no active file serving | Download UX |
| Q11 | Approvals for drafts/moves/bulk changes | No effects; approval records decision only | Action executor |
| Q12 | Hosted extraction packaging under the current Factory contract | Staged proposal, no copied Factory runtime | Shared binary extractor deployment |

Repository is private/proprietary by default. No OSS license has been granted to
this Product. Dependency license review remains part of release acceptance.

Future owner choices should become dated ADRs and close the matching backlog item.
Factory-specific requests are staged locally in `_FACTORY_CANDIDATES.jsonl` and
must receive Factory's own ADOPT/ADAPT/DEFER/REJECT disposition.
