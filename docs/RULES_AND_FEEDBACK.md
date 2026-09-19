# Rules and Feedback Control Plane

## Purpose

The control plane turns assistant/user feedback into governed system change. It distinguishes configuration, knowledge, and software capability so the live service learns without self-modifying.

## Three lanes

| Lane | Examples | Destination |
|---|---|---|
| Dynamic rule/config | sender/domain/category, priority, folder mapping, nudge interval | Versioned rules DB |
| Knowledge/state | person works at company, project membership, identity alias, preference | Temporal facts/entity review |
| Software change | new extractor/integration/schema/workflow/security behavior | Change request for Factory |

An assistant may propose in all lanes. It may not decide that a feature is “just a rule” when effects exceed the rule DSL.

## Rule model

A rule has scope, priority, typed predicates, effects, exceptions, risk, validity, provenance, and an immutable version. Predicates may inspect normalized headers, sender/domain/list ID, canonical entities, safe bounded text terms, attachment metadata, thread state, and prior classifications. Effects are allowlisted: annotate, categorize, assign project, set importance, request extraction, propose mailbox label/move, or suppress model escalation.

Example:

```yaml
kind: rule_proposal
scope: tenant
when:
  all:
    - sender_domain: melron.example
    - not: {header_flag: suspicious_sender_mismatch}
then:
  category: investment
  project_id: prj_melron
  importance: high
  mailbox: investments
reason: user confirmed an active investment relationship
evidence: [msg_123, correction_456]
```

The stored DSL is parsed into a safe AST. No arbitrary code, SQL, template execution, catastrophic regex, or network lookup.

## Decision tiers

### Auto-apply

Only low-impact, reversible metadata changes with strong evidence and policy authorization: verified alias, non-destructive tag, duplicate merge suggestion below display level, or learned synonym. Auto-apply thresholds are calibrated from real corrections, not model self-reported confidence.

### Review required

Anything changing attention or mailbox organization: VIP/always-read, `Needs Reply`, moving out of Inbox, `_GrokBot/Review Delete`, new sender/domain rule, entity merge, shared-project membership, or remote-model disclosure policy.

### Factory/security required

New extraction capability, provider/integration, table/schema, tool/API, scheduled workflow, automatic deletion/send, retention/security change, or executable behavior.

## Promotion from repeated behavior

The system aggregates correction evidence and proposes a rule only when:

- sufficient independent examples exist;
- protected/rare counterexamples are checked;
- expected precision and coverage are estimated;
- proposed scope is the narrowest useful one;
- a historical simulation shows affected messages and conflicts;
- review tier is determined by consequence.

Acceptance writes a new immutable version, records the simulation, and activates it at a known time. It does not rewrite code.

## Rule evaluation and conflicts

1. Global safety/protected-class policy.
2. Tenant explicit overrides.
3. Account-specific overrides.
4. Specific entity/sender/list rules.
5. General pattern rules.
6. Local-model classification.
7. Remote escalation.

“Keep/always surface” dominates “review delete.” Explicit user rules dominate learned rules unless forbidden by safety. Every outcome retains a human-readable trace showing matched conditions, competing rules, chosen effect, and versions.

## Review experience

Show the proposed behavior, why, supporting/counter evidence, estimated historical impact, affected accounts/folders, risk, expiry, and rollback plan. Allow approve, narrow, reject, defer, or mark “never suggest again.” Bulk approval is disabled for high-risk changes.

## Rollback and correction

- Deactivate the new version and reactivate the previous version atomically.
- Recompute affected derived classifications.
- Generate previewed compensating mailbox commands for reversible moves/labels.
- Never pretend a sent email or permanent deletion can be rolled back.
- Keep rejected/corrected model outputs as eval examples with privacy controls.

## Folder/label defaults

Canonical roles map per provider:

```text
_GrokBot/Review
_GrokBot/Review Delete
_GrokBot/Needs Reply
_GrokBot/Drafts
_GrokBot/Investments
_GrokBot/Travel
_GrokBot/Events
_GrokBot/Receipts
```

Gmail labels and Outlook/Fastmail/iCloud folders differ; connectors implement the canonical mapping. Initially, `Review Delete` stages mail only and never schedules automatic purge.

## Feedback quality metrics

Track proposal acceptance, narrowing, rejection, rollback, affected-message count, precision after activation, correction lag, remote-call reduction, and conflicting-rule frequency. Stop or quarantine a rule automatically on drift or protected-class counterexample—but require review to broaden it.
