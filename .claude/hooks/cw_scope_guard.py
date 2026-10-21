#!/usr/bin/env python3
"""pretooluse_scope_hook.py — the AGENT-LAYER twin of the Python scope guard.

THE TEMPLATE. `factory_launch.py install-hooks --product P` copies this file verbatim
to `<product>/.claude/hooks/cw_scope_guard.py` and registers it as a `PreToolUse` hook
in `<product>/.claude/settings.json` (matcher `Edit|Write|NotebookEdit|Read|Bash`).
It is never hand-copied: a hand-copied guard is a guard with N versions.
Template path is fixed by `factory_launch.HOOK_TEMPLATE_REL`.

WHY IT EXISTS. `_lib/scope_audit_hook.py` installs a `sys.addaudithook` handler, so it
sees every `open`/`sqlite3.connect`/`os.rename` a Python process performs. It cannot see
the agent's own `Read`/`Edit`/`Write` tool calls — those never enter a Python
interpreter that carries the guard. SESSION_CONTRACT §4(b) (L-F20; N4) is that gap.

**THE TWO LAYERS MUST BE INDEPENDENTLY COMPLETE.** The agent's `Bash` does NOT inherit
the launcher's exported binding environment, so `sitecustomize` is not on that path:
`sh -c 'python3 -c "open(...)"'` reaches the disk with no audit hook loaded. Anything
this layer waves through is unguarded, full stop. That is why the Bash rule below is an
allowlist of READERS and not a denylist of writers (E1_CRITIC B8: a write-verb denylist
let `python3` · `node` · `sqlite3` · `--out <factory>/x` straight through, because every
interpreter is a general-purpose writer and enumerating them is a losing game).

THE RULE IT ENCODES — SESSION_CONTRACT §4's exact scope, nothing stricter:

    WRITE-isolation to the Factory  +  READ/WRITE-isolation to every OTHER Product.

    Edit / Write / NotebookEdit / MultiEdit  under FACTORY_ROOT          -> DENY
    Bash that is not provably a READ         touching FACTORY_ROOT       -> DENY
    Read / Edit / Write / Bash               under another Product root  -> DENY
    Read (and allowlisted read-only Bash)    under FACTORY_ROOT          -> ALLOW
                                                (required, not tolerated)
    anything                                 under PRODUCT_ROOT          -> ALLOW

A path that is under both roots (a Product nested inside the Factory tree, which the
target structure forbids but a mis-registration could produce) resolves to ALLOW: the
bound Product's own root always wins, so the guard can never lock a session out of its
own repo.

THE BASH RULE, AND WHAT IT COSTS
--------------------------------
A command is classified by the paths it *resolves* to, not by the verbs it avoids:

  1. every path-shaped substring in every segment is resolved — absolute ones directly,
     relative ones against the payload's `cwd`, threaded through any `cd` in an earlier
     segment (`cd ../CW-Factory && rm README.md` is one command, not two);
  2. if anything lands under another Product          -> DENY, always;
  3. if anything lands under the Factory, the command must be provably read-only:
     EVERY segment's verb must be on `_READ_ONLY_VERBS` (a short, explicit list of
     readers), every `>`/`>>` target must land outside the Factory, and `git` must be
     on a read-only subcommand. Anything else — an unrecognised verb, ANY interpreter,
     an unparseable redirect — is DENIED.

**This fails closed, and the bill is false denials.** A Factory-touching command whose
verb is not on the list is refused even when it only reads: `python3 -c "print(open(
'<factory>/x').read())"`, `sed -n 1p <factory>/f`, `awk`,
`for f in <factory>/*; do …`, `xargs` chains, subshell plumbing. The remedy is always
available and is printed in the refusal: read it with `cat`/`head`/`grep`/`git show`,
or copy it into the Product first and process it there. That is a nuisance. A guard
that permits one interpreter write into the Factory is the entire defect — the trade is
not close.

HONEST LIMITS — WHAT THIS CHECK CANNOT SEE
------------------------------------------
Shell is not parseable by regex, and this is a text inspection running before the
command does. It will NOT see a Factory path that is:

  * built by variable expansion where the literal NEVER APPEARS in the command —
    `rm "$FACTORY"/x` (inherited from the environment), `rm "${HOME}/sys/<dir>/x"`.
    An assignment that spells the path out in the same command IS caught, because the
    scanner reads every segment: `F=../<factory-dir>; rm $F/x` denies on the literal in
    segment one. **Corrected 2026-08-20:** that sentence was true for a write VERB and
    false for a REDIRECT — `F=<factory>; echo x > $F/pwn` was allowed and the write
    landed. A `$`- or backtick-bearing token now resolves to nothing and is refused as
    unresolvable, so both forms deny. Only a value this command never states escapes;
  * produced by a substitution — `rm "$(cd ../CW-Factory && pwd)"/x`, backticks,
    `$(cat path.txt)`;
  * encoded or assembled — base64, `printf '%s'` concatenation, `tr`-rebuilt strings,
    a path read out of a file at runtime;
  * reached through a symlink INSIDE the Product that points at the Factory (the
    string resolves under the Product; `os.path.realpath` is applied to the resolved
    path, so a symlinked *component* that exists at classification time IS caught, but
    one created by the same command is not);
  * reached by a program the command merely starts — `make`, `npm run x`, a script in
    the Product whose body writes the Factory, a daemon, a background job;
  * inside a `cd` this scanner mis-tracks: `cd` in a subshell `( )` or via `pushd`,
    `cd -`, or a `cd` whose argument is itself a substitution (these mark the working
    directory UNKNOWN, and an unresolvable relative path then DENIES — but a command
    with no relative paths at all still passes).

Known false denials, measured, so nobody rediscovers them as bugs: `sed -n 1,20p
<factory>/f` · `awk 'NR<5' <factory>/f` · any pipeline whose LATER stage is an
interpreter (`cat <factory>/f | python3 -c …`) · `git -C <factory> branch --contains
HEAD` (a dual subcommand with an operand) · a Factory-touching `for`/`case` header,
whose first non-keyword token is a loop variable or a pattern rather than a verb
(`for i in <factory>/*` reports its verb as `i`) · any NON-read-only command naming a
regular file that has more than one hard link on a protected volume, whatever the
second link actually is — which covers a content-addressed store that hard-links into
the working tree (`.git/objects/…` after a local clone, a pnpm `node_modules`) as well
as a real laundering link. Every one has a plain-reader equivalent, which the refusal
names.

WHAT CHANGED 2026-09-20 (Sheet D: Q-445 · D3), each with a measured before/after in
`tests/gates/test_agent_hook_bypass_corpus.py`:

  * `jq` is ON the allowlist and `sed` is deliberately NOT (Q-445). See the comment
    at the `jq` entry for why the two differ.
  * ROOT COMPARISON IS CASE-FOLDED where the filesystem says it must be
    (`_fs_case_insensitive`, probed not assumed). `<factory-lowercased>/pwn.txt` was
    a different string for the same directory and the write landed.
  * A HARD LINK IS TREATED AS THE FILE IT SHARES (`_laundered_hardlink`). A second
    name for a Factory file, inside the Product, has nothing for `realpath` to
    resolve; a write through it landed.
  * A RESERVED WORD IS NOT A VERB (`_verb_of`). `if true; then rm -rf <factory>/…;
    fi` reported its verb as `then`, and the allowlist never saw `rm`.

WHAT CHANGED S196 (FACTORY-175), measured in
`tests/gates/test_agent_hook_output_operands.py`, which also pins the per-verb review:

  * A VERB ON THE ALLOWLIST IS READ, NOT TRUSTED. `uniq IN OUT` / `xxd IN OUT` (second
    operand), `tree -o`, `file -C`, `sort -uo`/`--out=`, `git --output=` all wrote and
    were allowed; they are detected now. `less`, `more`, `bat` left the list.
  * A READER THAT RUNS A PROGRAM IS NOT A READER. `git -c`/`--config-env`/
    `--exec-path=`, `git grep -O`, `git ls-remote --upload-pack`, bare `git stash`,
    `fd -x`, `rg --pre`, `ag/ack/delta --pager` — refused.
  * AN ASSIGNMENT IS PART OF THE COMMAND. `VAR=v reader` (and `env VAR=v`, and a
    bare `VAR=v;` segment) on a Factory-touching command is refused unless VAR is
    locale/display-only (`_SAFE_ENV`): `GIT_CONFIG_*` + `git status` wrote.
  New false denials, the same trade as the rest: `uniq "a b"` (a quoted operand with a
  space splits into two), `uniq F -c` (a flag after an operand is read the POSIX/BSD
  way, as an output name), `n=5; head -$n F`, `git -c color.ui=never log`. Each has a
  plain spelling the refusal names.

STILL OPEN, MEASURED, AND ON RECORD — all four are quoting/tokenising defects and all
four are what Q-449 (a real shell grammar under this policy layer) exists to close.
They are pinned as `xfail(strict=True)` in the corpus test, so closing one turns that
file red and forces the record to be corrected:

  * `cat <(rm <factory>/x)` and `cat >(rm <factory>/x)` — process substitution;
  * `rm -rf /Use"rs/…/CW-Factory/x"` — a quote INSIDE the path literal, which splits
    the token and hides the contiguous root from the second net (single-quote twin
    included);
  * `echo pwn > \\<factory>/pwn.txt` — a backslash in a redirect target, which makes
    the raw token non-absolute so it resolves against the Product.

Two layers stand behind those gaps and neither depends on text: `_lib/scope_audit_hook.py`
(every Python-mediated write, for the interpreters the launcher spawns) and
`factory_delta_check.py` (the after-the-fact tree receipt, AC-20). This layer raises the
cost of an accidental write to the Factory. It is not a sandbox and must never be cited
as one.

THE DENY IS GREPPABLE. Every refusal carries the literal marker

    CW-SCOPE-DENY

in `permissionDecisionReason` (stdout JSON) AND on stderr, followed by a `rule=` tag
(`factory-write` · `other-product` · `bash-factory-write` · `bash-other-product` ·
`no-cwd` · `unresolved-path` · `scope-unresolved`), the tool name, and the offending
path. The E7 soak's S5/S12 transcripts are captured by grepping that marker; do not
reword it without updating `tests/gates/test_agent_hook_negative.py` and
`tests/soak/operator_week.sh` in the same commit.

RELATIVE PATHS RESOLVE AGAINST THE PAYLOAD'S `cwd`, NOT THE HOOK PROCESS'S.
`os.path.abspath` in a hook resolves against whatever directory the harness happened to
launch the hook in — an unpinned assumption about someone else's runtime. The
`PreToolUse` payload carries `cwd`; that is the anchor. When a relative path needs an
anchor and the payload has none (or a relative one), the call is REFUSED (`rule=no-cwd`)
rather than guessed. Absolute paths need no anchor and are classified normally, so a
payload without `cwd` that only names absolute paths still works.

THE OTHER-PRODUCT DENYLIST IS BUILT AGAINST THE CANONICAL FACTORY, NOT THE RUNTIME.
`product.json`'s `repo.path` is relative TO THE FACTORY CHECKOUT (`../<product-dir>`).
Under a rollback the binding record's `factory_root` is `<factory>/.runtime/rollback-…`
(`factory_launch.verify` → `_resolve_runtime_root`), and joining a relative `repo.path`
against THAT yields `<factory>/.runtime/CW-X` — a directory that does not exist, so the
denylist silently came out empty and the guard guarded nothing (E1_CRITIC, hit live).
The anchor is therefore the CANONICAL root, derived by stripping the `.runtime/<name>`
suffix (`factory_rollback.RUNTIME_DIR_REL`) and confirming the parent looks like a
Factory. Both roots are treated as Factory for isolation purposes — under a rollback the
canonical checkout is still off-limits — and both `_SYSTEM/products/` directories are
read. **If any registered Product's root cannot be resolved, the denylist is INCOMPLETE
and the hook refuses everything it cannot prove is inside the bound Product**
(`rule=scope-unresolved`, marker `CW-SCOPE-DEGRADED`). An unresolvable Product path
quietly producing an empty denylist is the same fail-open pattern as the rest of B8.

WHAT THIS PROVES, AND WHAT IT DOES NOT
--------------------------------------
It proves: given a `PreToolUse` payload, this script returns the right decision.
It does NOT prove: that Claude Code loaded the hook, invoked it for a given tool, or
honoured the deny. That is agent-runtime behaviour with no mechanical channel back to
the Factory, and it is observable only in a real bound session — E7 soak S5 (the
refusal transcripts) and S12 (stub each guard once; every seeded refusal must turn RED).
`tests/gates/test_agent_hook_negative.py` tests the first sentence only, and says so.

FAILURE POLICY, DELIBERATE AND ARGUABLE. On an internal error — unparseable payload,
unreadable binding record, a bug here — this hook ALLOWS and prints a loud
`CW-SCOPE-HOOK-ERROR` / `CW-SCOPE-HOOK-INACTIVE` line to stderr. Rationale: a
`PreToolUse` hook that denies on its own malfunction can lock a session out of the very
files needed to repair it (including this hook and the binding record), and two
independent layers still stand behind it. The counter-case is real — a guard that fails
open is a guard an attacker only has to crash — so the failure is made LOUD rather than
silent, and the soak greps `CW-SCOPE-HOOK-` to catch a session that ran with the agent
layer inactive. Flip `_FAIL_OPEN` to False to invert it. Note the distinction: NO
binding is "inactive" (allow, loudly); a binding whose SCOPE cannot be fully resolved is
"degraded" (deny, loudly). The first is a session that has not started; the second is a
guard that would be lying.

READS: `<product>/_SYSTEM/_MEMORY/_ACTIVE_SESSION.json` (the binding record) and
`<factory>/_SYSTEM/products/*/product.json` (other Product roots). WRITES: nothing.
Stdlib only — it runs inside a Product checkout and must not import from the Factory.

Verbs: no arguments = hook mode (payload JSON on stdin). `selftest` = hermetic
self-check. `explain` = print the active scope it resolved, for debugging a session.
"""

import json
import os
import re
import stat
import sys
from pathlib import Path

DENY_MARKER = "CW-SCOPE-DENY"
ERROR_MARKER = "CW-SCOPE-HOOK-ERROR"
INACTIVE_MARKER = "CW-SCOPE-HOOK-INACTIVE"
DEGRADED_MARKER = "CW-SCOPE-DEGRADED"
CONTRACT_CITE = "SESSION_CONTRACT §4(b) — zero tolerance"

_FAIL_OPEN = True
SESSION_REL = Path("_SYSTEM") / "_MEMORY" / "_ACTIVE_SESSION.json"
RUNTIME_DIR_NAME = ".runtime"        # factory_rollback.RUNTIME_DIR_REL

WRITE_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
READ_TOOLS = ("Read",)
PATH_KEYS = ("file_path", "notebook_path", "path", "filePath")

# ── the Bash allowlist ────────────────────────────────────────────────────────
# Verbs that cannot write without a redirect (which is checked separately). NOT an
# exhaustive list of safe programs — an exhaustive list is impossible. It is the short
# list of readers a Factory-touching command is permitted to use; everything else,
# known or unknown, is denied. Adding an entry here is a security decision: the
# question is not "is this usually harmless" but "can this write a file at all".
_READ_ONLY_VERBS = {
    # navigation / metadata
    "cd", "pwd", "ls", "dir", "tree", "stat", "file", "du", "df", "basename",
    "dirname", "realpath", "readlink", "which", "whereis", "type", "find",
    # content readers
    #
    # FACTORY-175 (S196): every entry on this list was reviewed for a write form; the
    # verdicts are held in `tests/gates/test_agent_hook_output_operands.py::REVIEWED`,
    # which goes red if a verb is added here without one. Four verbs WRITE through an
    # operand or flag and are detected in `_verb_is_read_only` (`uniq IN OUT`,
    # `xxd IN OUT`, `tree -o/-R`, `file -C`; `sort -o` was already there and is now
    # read in clusters and abbreviations too). Three were REMOVED instead: `less` and
    # `more` copy their input to a log file (`-o/-O FILE`), and `bat` writes a config
    # file and a cache — and none of the three is needed to read a file in a
    # non-interactive shell, where `cat`/`head` do the whole job.
    "cat", "head", "tail", "nl", "strings", "xxd", "od",
    "hexdump", "wc", "cut", "column", "fold", "rev", "sort", "uniq", "comm",
    "join", "paste", "tr", "expand", "unexpand", "tac",
    # Q-445, ruled 2026-09-20: `jq` is admitted and `sed` is HELD.
    #
    # `jq` has no way to write a file. Its whole output surface is stdout (a
    # redirect is checked separately, by the same rule as every other verb) and
    # every file-shaped flag it takes is an INPUT: `-f/--from-file` (the program),
    # `--rawfile`, `--slurpfile`, `--argfile`. There is no `-i`, no `--in-place`,
    # no output-file flag. It passes the allowlist's actual question — "can this
    # write a file at all" — with a no.
    #
    # `sed` fails that question three ways and stays DENIED until the write
    # detector can see all three: `sed -i` (in-place), `sed -n 'w FILE'` (the `w`
    # COMMAND), and `s/a/b/w FILE` (the `w` FLAG on a substitution). Only the first
    # has a detector here (`_INPLACE_EDIT`), and it is a regex over the raw command
    # — the same text-inspection that six parser rounds could not make sound. The
    # other two hide a destination inside a quoted script argument, which is a
    # SHELL-GRAMMAR problem (Q-449), not an allowlist problem. Admitting `sed` is
    # therefore blocked on Q-449 landing, not on anyone's appetite.
    "jq",
    # search
    "grep", "egrep", "fgrep", "zgrep", "rg", "ag", "ack", "fd", "locate",
    # compare / digest
    "diff", "cmp", "colordiff", "delta", "md5", "md5sum", "shasum", "sha1sum",
    "sha256sum", "cksum",
    # trivial builtins
    "echo", "printf", "true", "false", "test", "[", ":", "date", "sleep", "wait",
    # version control, read subcommands only (subtracted below)
    "git",
}
# Shell keywords that start a segment but execute nothing themselves; the segment they
# introduce is scanned on its own.
_SHELL_KEYWORDS = {
    "if", "then", "elif", "else", "fi", "for", "while", "until", "do", "done",
    "case", "esac", "in", "select", "function", "{", "}", "(", ")", "!", "&&", "||",
}
_WRAPPERS = {"sudo", "env", "command", "nohup", "time", "xargs", "builtin", "exec",
             "stdbuf", "nice", "ionice", "timeout"}
# A wrapper operand that cannot be a command name: a bare number, or a number with a
# duration suffix (`timeout 5s`, `timeout 1.5m`). Used only to step over a wrapper's
# own arguments while hunting the real verb — see `_verb_of`.
_DURATION_RE = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")

_GIT_READ_SUBCOMMANDS = {
    "log", "show", "status", "diff", "blame", "rev-parse", "rev-list", "for-each-ref",
    "cat-file", "ls-files", "ls-tree", "ls-remote", "describe", "shortlog", "grep",
    "count-objects", "var", "help", "whatchanged", "name-rev", "check-ignore",
    "verify-pack", "diff-tree", "diff-index", "merge-base",
}
# Subcommands that read with no operand and WRITE with one (`git branch` lists,
# `git branch x` creates). Allowed only when every remaining token is a read flag.
_GIT_DUAL_SUBCOMMANDS = {"branch", "tag", "remote", "worktree", "submodule",
                         "notes", "config"}     # `stash` left (S196): see _git_is_read_only
_GIT_DUAL_READ_TOKENS = {
    "list", "-v", "-vv", "--verbose", "-a", "--all", "-l", "--list", "--show-current",
    "-r", "--remotes", "--merged", "--no-merged", "--get", "--get-all", "--porcelain",
}
_FIND_WRITE_FLAGS = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint",
                     "-fprint0", "-fprintf", "-fls"}

_INPLACE_EDIT = re.compile(r"\b(sed|perl|ruby|awk|python3?)\b[^|;&]*\s-[a-zA-Z]*i\b")
# Any `>` / `>>` that is not a `>&` duplication. `2>file` IS a write; `2>&1` is not.
_REDIRECT_TARGET = re.compile(r">{1,2}(?![&(])\s*([^\s;|&)<>'\"]+)?")
# A run of path-shaped characters. Deliberately excludes quotes, commas, parentheses
# and `=` so a path embedded in quoted interpreter source — `open('../F/x','w')`,
# `--out=<factory>/x` — is still recovered as its own candidate.
_PATHISH = re.compile(r"[A-Za-z0-9_.~/@+-]+")
_SEGMENT = re.compile(r"[|;&\n]+|\$\(|`")
# A file-descriptor DUPLICATION — `2>&1`, `>&2`, `1>&-` — writes no file. It must be
# removed before `_SEGMENT` splits on `&`: split first, and `2>&1` becomes a segment
# ending in a bare `2>` whose target parses as empty, so `ls 2>&1 | head` was refused
# as an "unparseable redirect" (S174, found when the Factory-direction twin of this
# hook denied its own author's routine commands). `&>file` and `>&file` are NOT
# matched: the target there is a file, and it still reaches `_REDIRECT_TARGET`.
_FD_DUP = re.compile(r"\d*>&(?:\d+|-)(?=$|[\s;|&)])")
# `>&word` with a non-numeric word is bash's "stdout AND stderr to FILE" — a real file write.
# Split on `&` it parsed as an empty target and was refused even when harmless (reviewer,
# S174). Rewritten to `> word` before splitting, so the target is resolved and classified
# like any other redirect — still refused when it lands under a protected root.
_AMP_FILE = re.compile(r"\d*>&(?=[^\s\d&-])")
# `cmd <<'EOF'` … `EOF` (quoted or not, `<<-` allowed). Group 3 is the body.
_HEREDOC = re.compile(r"<<-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)",
                      re.DOTALL)


def _quoted_spans(text: str):
    """(start, end) of every quoted run — the regions where shell OPERATORS are data.

    A `>` inside quotes redirects nothing. `git commit -m "… <noreply@anthropic.com>"`
    has a `>` followed by a closing quote, which `_REDIRECT_TARGET` read as a redirect
    with an EMPTY target, i.e. "unparseable", i.e. DENIED — so a routine attributed
    commit was refused twice in one session and had to be routed through a message file.
    Same class as the heredoc fix above: shell structure must not be read out of data.

    Deliberately narrow. Only the redirect scan consults this; `_PATHISH` still reads the
    raw segment, so a quoted path inside interpreter source is recovered exactly as
    before. A REAL redirect's operator is never inside quotes — `echo x > "/p/f"` has its
    `>` outside — so nothing that writes stops being seen."""
    return _quoted_spans_ex(text)[0]


def _quoted_spans_ex(text: str):
    """(spans, unterminated). The scanner, plus an honest report of whether it coped.

    `unterminated` is True when a quote ran off the end of the text, which means every
    span after it is guesswork. `_split_segments` uses that to fall back; the redirect
    scan does not, because there a mis-paired span costs at most a missed `>` that the
    verb allowlist still catches.

    ANSI-C `$'…'` IS MODELLED, and the omission was a real bypass:
    `echo "$(echo $'\\'"'; touch <factory>/PWNED)"` — inside `$'…'` a backslash-escaped
    quote does NOT close the string, but the plain single-quote branch stopped there, and
    the bogus span covered both the real `)` and the `;`. Found by a randomized structural
    fuzz once `$'` was added to its alphabet: 16,183 commands, one regression, this one."""
    spans, i, n, unterminated = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch in "'\"":
            ansi_c = ch == "'" and i > 0 and text[i - 1] == "$"
            j = i + 1
            while j < n and text[j] != ch:
                j += 2 if (text[j] == "\\" and (ch == '"' or ansi_c)) else 1
            if j >= n:
                unterminated = True         # unterminated: treat the rest as UNQUOTED
                break
            spans.append((i, j))
            i = j + 1
            continue
        i += 1
    return spans, unterminated
def _spans_trustworthy(chunk: str, spans: list, unterminated: bool) -> bool:
    """Can `_quoted_spans` be trusted to SEGMENT this chunk? Conservative on doubt.

    THE SHAPE OF THIS GUARD MATTERS MORE THAN ITS CONTENTS. `_quoted_spans` is an
    approximation of shell quoting, and it was written for a narrow, fail-closed job:
    suppressing REDIRECT detection, where a mis-paired span costs at most a missed `>`
    that the verb allowlist still catches. Using it to decide segmentation promoted it to
    an authority it was never audited for — a mis-pair there hides a whole command from
    the verb check. Five bypasses were found and fixed in the splitter; the sixth was in
    this scanner, untouched and newly load-bearing.

    So rather than chase the seventh, the loosening is made conditional on the scanner's
    own competence: a chunk carrying a construct it does not model suppresses NOTHING and
    falls back to the unfixed behaviour for that chunk. Every future member of this class
    is then a false denial — a nuisance report — instead of a deleted `_SYSTEM`.

    THE TRIGGER LIST IS A COMPLEMENT, NOT A DENYLIST, and that is the difference between
    this and a list that grows by one every time someone finds another bypass. Bash
    introduces a region where text is not executed in an enumerable set of ways — the
    manual's QUOTING section has exactly four (`\\`, `'…'`, `"…"`, `$'…'`), plus
    `$"…"` which is quoting-identical to `"…"`, plus two that are not quoting at all: a
    `#` comment, and a here-document. The scanner models the four. Here-documents are cut
    out before `_split_segments` ever sees the text. That leaves `#`, and "the scanner ran
    off the end" — which is this list. So a NEW member of this class means bash grew a
    quoting form, and this docstring is where that has to show up.

    Read that as a claim to check, not a proof: it is written from the manual's structure
    rather than verified against the manual in this session, and if it is wrong the
    closure is worse than an honest denylist would have been. What does not depend on it
    is the direction — an unmodelled construct costs a false denial here, never a bypass.

      * an UNTERMINATED quote — every span after it is guesswork;
      * a `#` COMMENT START outside the spans with a quote character after it. A comment's
        contents are data, so an apostrophe in one shifts the parity of everything that
        follows. Deliberately not "any `#`": `git commit -m "fix: don't #1"` has its `#`
        inside a span and stays fixed, which is the whole point of the change.

    The `#` trigger is INSURANCE, and an ablation says so honestly: removing it changed no
    outcome across a 55,591-command quote-density fuzz, because a chunk carries no newline,
    so a comment runs to the end of it and nothing after the `#` executes at this level.
    The cross-chunk case that actually bit — `echo ok # it's fine` then a newline — is
    handled by the newline being a level reset. It is kept because it is monotone in the
    safe direction and it is the one trigger that would catch a `#` reaching further than
    this reasoning expects. It is not dead: it changes 6 decisions in 2,489, every one of
    them toward deny.
    """
    if unterminated:
        return False
    for m in re.finditer(r"(?:(?<=\s)|^)#", chunk):
        if any(a <= m.start() <= b for a, b in spans):
            continue                        # a `#` inside quotes is data, not a comment
        if any(c in chunk[m.start():] for c in "'\""):
            return False                    # the comment can shift quote parity after it
    return True


def _literal_separator_spans(text: str) -> list:
    """Spans of `text` where `;` `|` `&` are LITERAL, for text at ONE shell level.

    `text` must already be free of `$(`, a backtick and a newline — `_split_segments`
    guarantees that by splitting on those first. It matters: a substitution and a newline
    each RESET quoting, so pairing quotes across one mis-pairs them. Both halves of that
    were found by running commands rather than reading them, and both really wrote.
    The `$(`/backtick guard below is therefore belt-and-braces, not the mechanism."""
    spans, unterminated = _quoted_spans_ex(text)
    if not _spans_trustworthy(text, spans, unterminated):
        return []                           # suppress nothing: fall back to splitting all
    out = []
    for a, b in spans:
        if text[a] == '"' and ("$(" in text[a + 1:b] or "`" in text[a + 1:b]):
            continue
        out.append((a, b))
    return out


# Openers that START A NEW SHELL LEVEL, plus the newline that ends a command. Splitting on
# these is unconditional, and each one RESETS quoting for what follows.
_LEVEL_RESET = re.compile(r"\n+|\$\(|`")
# The separators that a quoted run can legitimately contain as data.
_INLINE_SEP = re.compile(r"[|;&]+")


def _level_exit(chunk: str) -> int:
    """Offset of the first `)` that leaves this shell level, or len(chunk) if none.

    THE THIRD AND FOURTH PARITY FAILURES, and why this is a position rather than a flag. A
    chunk begins after a `$(`, a backtick or a newline, so its quoting starts clean — but
    nothing ended it. `)` returns to the ENCLOSING level, where a quote may still be open,
    and past that point the chunk's own pairing is offset by whatever the parent left
    open. Measured by a reviewer's differential oracle against real bash:

        echo "$(echo "$(echo "x")"; rm -rf <factory>/CLAUDE.md)"

    The last chunk is `echo "x")"; rm -rf …)"`. Four quotes, so it pairs cleanly on its own
    terms — and wrongly: the `"` that CLOSES the outer string reads as an opener, pairs
    with the trailing one, and the span swallows the `;`. One `echo` segment, and
    CLAUDE.md really went.

    PARENS ARE COUNTED ONLY WHERE THEY ARE SHELL. The first version of this walked the raw
    text, so one paren inside quoted DATA pushed the exit past the real one and the whole
    hole reopened one character later:

        echo "$(echo "$(echo "(")"; touch <factory>/PWNED)"

    195 of those in a 900-case corpus. Masking the quoted spans first is the same
    principle this file already applies to `>` and to the separators themselves: shell
    structure is never read out of data. Backslash escapes are skipped for the same
    reason — a backslash-escaped paren is data too.

    Counting quote parity does not catch either shape (the depth-3 chunk's count is even).
    Adding `)` to the level resets would, and would also split
    `git commit -m "fix (a); do b"` — the false denial this whole change exists to remove.
    So the rule is positional: suppress only BEFORE the first level exit. Text at this
    level keeps the fix; text past the exit reverts to splitting on everything, exactly as
    before the change. Never less safe than the unfixed guard, anywhere.
    """
    spans = _quoted_spans(chunk)
    depth, i, n = 0, 0, len(chunk)
    while i < n:
        ch = chunk[i]
        if ch == "\\":
            i += 2                       # an escaped paren is data, and so is what follows
            continue
        if any(a <= i <= b for a, b in spans):
            i += 1                       # inside quotes: a paren is data, not structure
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return i
            depth -= 1
        i += 1
    return n


def _split_segments(text: str) -> list:
    """`_SEGMENT.split`, except that a separator INSIDE QUOTES is data, not structure.

    `;`, `|` and `&` inside a quoted run separate nothing — the shell hands the whole run
    to the command as one argument. Splitting on them invented segments out of an
    argument's contents, and the invented segment's first word was then classified as a
    command verb. Measured 2026-09-23 (BG-FC-2026-09-23-01): a valid `factory_launch.py`
    call carrying a quoted `;` in one argument was DENIED, because the text after the `;`
    parsed as a second command whose verb was not on the read-only allowlist.

    TWO LEVELS, AND THE SECOND ONE IS WHY THIS IS SAFE. Quoting is not a property of the
    whole command string; it restarts inside every `$(…)` and after every newline. This
    was written three times and an adversarial oracle broke the first two, each time with
    a command that really deleted a Factory file:

      * `echo "$(echo t | tee <factory>/x)"` — a substitution inside double quotes IS
        shell, so its `|` is real. Version 1 suppressed it and allowed the write.
      * `echo ok # it's fine` + newline + `echo pwn > '<factory>/pwn.txt'` — `#` ends at
        the newline, but a whole-text scan paired the comment's apostrophe with line two's
        opening quote and swallowed the newline, the `>` and the path.
      * `echo "$(ls "."; rm -rf <factory>/_SYSTEM)"` — version 2 dropped the OUTER span
        for containing `$(`, then mis-paired the INNER `"` with the trailing one, yielding
        a second span that held the `;` and no `$(`. One `echo` segment; `_SYSTEM` gone.

    So the split is done in two passes: first on the level resets, unconditionally; then
    `;`/`|`/`&` within each resulting chunk, against spans computed FOR THAT CHUNK. A
    chunk contains no substitution and no newline by construction, so its quotes pair the
    way the shell pairs them.

    WHY THE REMAINING LOOSENING DOES NOT WEAKEN THE GUARD. A quoted separator cannot
    smuggle a write, because the ENCLOSING command's own verb still has to pass:
      * `bash -c "cd <factory>; rm -rf x"` — one segment, verb `bash`, not on
        `_READ_ONLY_VERBS`, so it denies. Before it denied on the invented `rm` segment;
        after, it denies on the real verb. Same answer, better reason.
      * `python3 -c "…; …"` — `python3` is deliberately absent from the allowlist, and the
        launcher exemption refuses any leading interpreter flag, so `-c` cannot reach it.
      * `echo "a; rm -rf <factory>"` — verb `echo`, read-only, and `echo` really does not
        execute that text. Allowed, correctly; `_PATHISH` still resolves the Factory path
        inside the quotes and records the touch as a READ.
    The one behaviour that genuinely changes is the launcher exemption's "exactly one
    verb" rule: an argument's quoted `;` no longer manufactures a second verb that revoked
    it. A real `&&`, `;` or pipe is outside quotes and splits exactly as before.
    """
    out = []
    chunks, last = [], 0
    for m in _LEVEL_RESET.finditer(text):
        chunks.append(text[last:m.start()])
        last = m.end()
    chunks.append(text[last:])
    for chunk in chunks:
        spans = _literal_separator_spans(chunk)
        exit_at = _level_exit(chunk)
        last = 0
        for m in _INLINE_SEP.finditer(chunk):
            if (m.start() < exit_at
                    and any(a < m.start() < b for a, b in spans)):
                continue              # a separator inside quotes is part of an argument
            out.append(chunk[last:m.start()])
            last = m.end()
        out.append(chunk[last:])
    return out


_PATH_BOUNDARY = re.compile(r"[A-Za-z0-9_.~@+-]")


# ───────────────────────────── scope resolution ───────────────────────────────

def _norm(p, base=None) -> str:
    """Absolute, symlink-resolved, case-normalised. `base` anchors a relative path;
    without one a relative path is resolved against the PROCESS cwd, which is why
    every caller that can be handed a relative path passes an explicit base."""
    if not p:
        return ""
    try:
        p = os.path.expanduser(str(p))
        if base and not os.path.isabs(p):
            p = os.path.join(base, p)
        return os.path.normcase(os.path.realpath(os.path.abspath(p)))
    except (OSError, ValueError):
        return ""


_CI_CACHE = {}


def _fs_case_insensitive(root: str) -> bool:
    """Does the filesystem holding `root` treat two spellings as one file?

    DETECTED, never assumed. `os.path.normcase` is the identity on POSIX and
    `os.path.realpath` does NOT canonicalise case, so on macOS's default
    case-INSENSITIVE APFS a lower-cased spelling of the Factory root is a
    different STRING for the same DIRECTORY — and `startswith` said "not under
    the Factory" while bash wrote into it (D3, measured: `echo pwn >
    <factory-lowercased>/pwn.txt` was ALLOWED and the byte landed).

    Hard-coding "darwin means case-insensitive" would be the wrong fix twice
    over: a case-SENSITIVE APFS volume exists and is a supported format, and a
    Linux box can mount a case-insensitive volume. So this probes the actual
    filesystem, read-only: walk up to a component that exists and has a letter
    to flip, flip its case, and ask whether the two names are the same inode.
    A probe that cannot be made (no letters, no readable parent, an OSError)
    answers False — the STRICTER of the two, since a False here only means the
    comparison stays exact.
    """
    if root in _CI_CACHE:
        return _CI_CACHE[root]
    result = False
    probe = root
    while probe and probe != os.sep:
        if os.path.exists(probe):
            head, tail = os.path.split(probe)
            alt = tail.swapcase()
            if alt != tail and head:
                try:
                    result = os.path.samefile(probe, os.path.join(head, alt))
                except (OSError, ValueError):
                    result = False
                break
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    _CI_CACHE[root] = result
    return result


def _under(path: str, root: str) -> bool:
    if not path or not root:
        return False
    if _fs_case_insensitive(root):
        path, root = path.lower(), root.lower()
    return path == root or path.startswith(root + os.sep)


def _protected_devices(scope: dict) -> set:
    """`st_dev` of every root this guard protects, computed once per scope."""
    cached = scope.get("_devices")
    if cached is not None:
        return cached
    devices = set()
    for root in list(scope.get("factory_roots") or []) + list(
            scope.get("other_roots") or []):
        try:
            devices.add(os.stat(root).st_dev)
        except OSError:
            continue
    scope["_devices"] = devices
    return devices


def _laundered_hardlink(path: str, scope: dict) -> bool:
    """Is `path` a SECOND NAME for a file that also lives under a protected root?

    A hard link has nothing for `os.path.realpath` to resolve — the two names
    are peers, not a link and a target — so every path-string rule in this file
    is blind to it (D3, measured: `ln <factory>/victim.txt ./hl.txt` denies,
    but once `./hl.txt` exists, `echo pwn > ./hl.txt` names no Factory path at
    all, was ALLOWED, and the byte landed in the Factory's inode).

    Proving the link is cheap only in one direction: a regular file with
    `st_nlink > 1` on the same DEVICE as a protected root MIGHT be a second name
    for a file under it, and enumerating the other names would mean walking the
    whole Factory tree on every Bash call. So this answers "could be", and the
    caller refuses — the same fail-closed trade the rest of this hook makes.

    The bill, stated so nobody rediscovers it as a bug: a Product file that is
    hard-linked to another Product file on the same volume denies too, and so
    does a `.git/objects/…` path in a repo cloned locally (git hard-links
    objects). Directories are excluded outright — `st_nlink` counts subdirectory
    entries, so every directory on HFS+/APFS would otherwise read as linked.
    """
    if not path:
        return False
    try:
        st = os.lstat(path)
    except (OSError, ValueError):
        return False
    if not stat.S_ISREG(st.st_mode) or st.st_nlink < 2:
        return False
    return st.st_dev in _protected_devices(scope)


def product_root_guess() -> str:
    """Where this hook believes the Product is.

    `PRODUCT_ROOT` when the environment carries a binding; otherwise the hook file's
    own location (`.claude/hooks/<me>.py` -> two levels up). The `__file__`-derived
    fallback is exactly the pattern SESSION_CONTRACT §4(c) forbids in *Factory tools*,
    and it is correct HERE for the opposite reason: this file is installed INSIDE one
    Product, it is not shared, and the agent process that runs a `PreToolUse` hook does
    not inherit the launcher's exported binding environment. Resolving through
    `product_paths.product_root()` is impossible — that import would reach into the
    Factory from a Product-local hook.

    NOTE THE ASYMMETRY, WHICH IS THE WHOLE POINT: this locates the BINDING RECORD, not
    the Factory. Every root the guard enforces against — factory_root, the canonical
    checkout behind a rollback runtime, every other Product — is read OUT of that
    record and never inferred from where this copy of the file happens to sit. A
    template copied into a Product cannot ask its own location where the Factory is;
    that answer would be a path inside the Product.
    """
    env = os.environ.get("PRODUCT_ROOT")
    if env:
        return _norm(env)
    return _norm(Path(__file__).resolve().parents[2])  # factory-root: see above —
    # this locates the BINDING RECORD inside the Product this hook was installed in,
    # which no record can supply; every ENFORCED root comes from the record.


def canonical_factory_root(runtime_root: str) -> str:
    """The canonical checkout behind a (possibly rollback) runtime root.

    `factory_rollback.engage` materialises `<factory>/.runtime/rollback-<date>/` and
    `factory_launch._resolve_runtime_root` hands that to `bind`, which records it as
    `factory_root`. Relative `repo.path` values in `product.json` are relative to the
    CANONICAL checkout, so that is the anchor: strip a trailing `.runtime/<name>` and
    confirm the result still looks like a Factory. Anything else is returned unchanged.
    """
    if not runtime_root:
        return ""
    parts = runtime_root.split(os.sep)
    if RUNTIME_DIR_NAME not in parts:
        return runtime_root
    idx = len(parts) - 1 - parts[::-1].index(RUNTIME_DIR_NAME)
    candidate = os.sep.join(parts[:idx]) or os.sep
    if not candidate or candidate == runtime_root:
        return runtime_root
    looks_like_factory = (os.path.isfile(os.path.join(candidate, "FACTORY.md"))
                          or os.path.isdir(os.path.join(candidate, "_SYSTEM")))
    return _norm(candidate) if looks_like_factory else runtime_root


def _other_roots(factory_roots, bound_product):
    """(other_roots, unresolved). `unresolved` is non-empty when a registered Product's
    root could not be pinned down — which makes the denylist a LIE, not a shorter list."""
    other, unresolved, seen_ids = [], [], set()
    for froot in factory_roots:
        pdir = Path(froot) / "_SYSTEM" / "products"
        if not pdir.is_dir():
            continue
        for entry in sorted(pdir.iterdir()):
            pj = entry / "product.json"
            if not pj.is_file():
                continue
            try:
                data = json.loads(pj.read_text())
            except (ValueError, OSError) as e:
                unresolved.append(f"{entry.name}: unreadable product.json ({e})")
                continue
            repo = data.get("repo")
            path = repo.get("path") if isinstance(repo, dict) else repo
            if not path:
                unresolved.append(f"{entry.name}: product.json has no repo.path")
                continue
            path = os.path.expanduser(str(path))
            if os.path.isabs(path):
                candidates = [_norm(path)]
            else:
                # relative TO THE FACTORY CHECKOUT — never to the agent's cwd, and
                # never to a rollback runtime directory (L-F26 / E1_CRITIC).
                candidates = [_norm(path, base=str(r)) for r in factory_roots]
                candidates = [c for c in candidates if c]
                existing = [c for c in candidates if os.path.isdir(c)]
                if existing:
                    candidates = existing[:1]
                elif candidates:
                    unresolved.append(
                        f"{entry.name}: relative repo.path {path!r} resolves to no "
                        f"existing directory (tried {', '.join(candidates)})")
            for r in candidates:
                if r and r != bound_product and not _under(r, bound_product) \
                        and r not in other:
                    other.append(r)
            seen_ids.add(entry.name)
    return other, unresolved


def load_scope():
    """Resolve `{product_root, factory_roots, other_roots, unresolved}` from the
    binding record.

    Returns `(scope_dict, note)`. `scope_dict` is None when there is no usable binding
    — meaning the guard is INACTIVE and every call is allowed; `note` says why. A scope
    that resolved but could not enumerate every other Product comes back with a
    non-empty `unresolved`, which DENIES rather than allows (see `decide`).
    """
    proot = product_root_guess()
    if not proot:
        return None, "cannot resolve the Product root from this hook's location"
    rec_path = Path(proot) / SESSION_REL
    if not rec_path.is_file():
        return None, (f"no binding record at {rec_path} — the session has not run "
                      "`Q: Start` / `factory_launch.py bind` yet")
    try:
        rec = json.loads(rec_path.read_text())
    except (ValueError, OSError) as e:
        return None, f"binding record unreadable ({type(e).__name__}: {e}): {rec_path}"

    runtime_root = _norm(rec.get("factory_root"))
    bound_product = _norm(rec.get("product_root")) or proot
    if not runtime_root:
        return None, f"binding record has no factory_root: {rec_path}"

    canonical = canonical_factory_root(runtime_root)
    factory_roots = [runtime_root] + ([canonical] if canonical != runtime_root else [])
    other, unresolved = _other_roots(factory_roots, bound_product)
    return ({"product_root": bound_product,
             "factory_root": runtime_root,          # the bound runtime, for messages
             "factory_roots": factory_roots,        # runtime AND canonical
             "other_roots": other,
             "unresolved": unresolved,
             "record": str(rec_path)}, "")


# ─────────────────────────────── classification ───────────────────────────────

def _tool_paths(tool_name: str, tool_input: dict) -> list:
    out = []
    for key in PATH_KEYS:
        v = tool_input.get(key)
        if isinstance(v, str) and v:
            out.append(v)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for e in edits:
            if isinstance(e, dict):
                for key in PATH_KEYS:
                    v = e.get(key)
                    if isinstance(v, str) and v:
                        out.append(v)
    return out


def _classify(path: str, scope: dict) -> str:
    """'other' | 'product' | 'factory' | '' for one resolved absolute path."""
    if not path:
        return ""
    for root in scope["other_roots"]:
        if _under(path, root):
            return "other"
    if _under(path, scope["product_root"]):
        return "product"                 # the bound Product always wins
    for root in scope["factory_roots"]:
        if _under(path, root):
            return "factory"
    return ""


def _root_mentioned(command: str, root: str) -> str:
    """Literal occurrence of `root` in `command`, at a path boundary. Substring
    matching is the second net under `_PATHISH` token resolution: it catches an
    absolute root embedded in a token shape the tokeniser does not recover. The
    boundary check keeps a root `/x/CW-Alpha` from matching `/x/CW-AlphaBeta/f`."""
    if not root:
        return ""
    low, rlow = command.lower(), root.lower()
    start = 0
    while True:
        i = low.find(rlow, start)
        if i < 0:
            return ""
        end = i + len(rlow)
        if end >= len(low) or not _PATH_BOUNDARY.match(low[end]):
            return root
        start = i + 1


def _tokens(segment: str) -> list:
    return [t.strip("'\"") for t in segment.split() if t.strip("'\"")]


def _verb_of(tokens: list):
    """(verb, remaining args), skipping `VAR=value` prefixes, wrappers AND the
    reserved words that merely INTRODUCE a command.

    A RESERVED WORD IS NOT A VERB. `_verb_is_read_only` waves through anything in
    `_SHELL_KEYWORDS`, which is correct for a segment that really is only a keyword
    (`fi`, `done`, `esac`) and was catastrophic for one that is a keyword followed by
    a command: `_SEGMENT` splits `if true; then rm -rf <factory>/_SYSTEM; fi` into
    `if true` / `then rm -rf <factory>/_SYSTEM` / `fi`, and the middle segment
    reported its verb as `then` — a keyword — so the allowlist never saw `rm`.

    Measured 2026-09-20 against real bash over a 14,216-command corpus: `if`, `for`,
    `while`, `until` and `case` bodies were ALLOWED with a plain absolute Factory path
    and every write landed. This is not a parsing defect — the segmentation was right
    and the words were right; the POLICY read the wrong token as the verb. Skipping
    keywords the way wrappers are already skipped is the whole fix.

    What it costs, and why the cost is bounded: `for i in <factory>/*` now reports its
    verb as `i`, which is not on the allowlist, so that loop denies. The verb
    allowlist is consulted ONLY for a command that already touches a protected root
    (`decide`), so nothing confined to the Product is affected — and a Factory-touching
    `for` loop was already on the docstring's measured false-denial list.
    """
    i = 0
    while i < len(tokens):
        t = tokens[i].lstrip("({")
        if not t:
            i += 1
            continue
        if "=" in t and not t.startswith("-") and "/" not in t.split("=")[0]:
            i += 1                                   # VAR=value prefix
            continue
        verb = os.path.basename(t)
        if verb in _WRAPPERS or verb in _SHELL_KEYWORDS:
            i += 1
            # A WRAPPER'S OWN ARGUMENTS ARE NOT THE VERB. Skipping only the wrapper
            # token leaves its operand in the verb slot: `timeout 180 python3 …`
            # resolved its verb to `180`. That is on no allowlist, so a plain READ of
            # a Factory path was refused AND the armed entry-tool exemption was lost —
            # `timeout 180 python3 deployment_gate.py <product>` denied for the wrong
            # reason. The row that found this named `timeout`; the defect is the class
            # (`nice -n 5`, `ionice -c 3`, `stdbuf -oL`, `sudo -u jim`), so the skip is
            # written against the class.
            #
            # Two shapes are skipped, and only two: a token starting with `-` (a flag,
            # never a command name), and a token that is purely a number or a
            # number+unit duration (`180`, `5s`, `1.5m` — never a command name either).
            # Anything else ends the skip, so the first real word still wins the verb
            # slot. The fix can only ever RESOLVE A TRUER VERB, never skip past a real
            # command: both skipped shapes are unrunnable as commands. Direction check —
            # `timeout 5 rm -rf <factory>` denied before (verb `5`, unlisted) and denies
            # after (verb `rm`, unlisted); what changes is that the refusal is now for
            # the right reason and the read cases stop being false denials.
            while i < len(tokens):
                nxt = tokens[i]
                if nxt.startswith("-") or _DURATION_RE.match(nxt):
                    i += 1
                    continue
                break
            continue
        return verb, tokens[i + 1:]
    return "", []


def _env_assignments(tokens: list) -> list:
    """The NAMES a segment assigns ahead of its verb — `VAR=v cmd`, `env VAR=v cmd`, or
    a segment that is nothing but `VAR=v`. Walks the tokens exactly as `_verb_of` does,
    so every assignment `_verb_of` steps over to find the verb is reported here.

    WHY (found in the FACTORY-175 review, S196). `_verb_of` skips assignments — right
    for finding the verb, and it left them invisible to the policy. An environment
    variable can make a READER run a program: `GIT_CONFIG_COUNT=1
    GIT_CONFIG_KEY_0=core.fsmonitor GIT_CONFIG_VALUE_0=<product>/x.sh git -C
    <factory> status` ran x.sh (measured: the write landed under bash AND zsh, and the
    guard allowed it). `GIT_EXTERNAL_DIFF`, `PAGER`, `PYTHONPATH` are the same class."""
    names, i = [], 0
    while i < len(tokens):
        t = tokens[i].lstrip("({")
        if not t:
            i += 1
            continue
        if "=" in t and not t.startswith("-") and "/" not in t.split("=")[0]:
            names.append(t.split("=", 1)[0])
            i += 1
            continue
        if os.path.basename(t) in _WRAPPERS or os.path.basename(t) in _SHELL_KEYWORDS:
            i += 1
            while i < len(tokens) and (tokens[i].startswith("-")
                                       or _DURATION_RE.match(tokens[i])):
                i += 1
            continue
        break
    return names


# Variables that only change locale, colour or layout — the one set a Factory-touching
# command may assign. Everything else is refused: enumerating the variables that run
# code (GIT_*, *PAGER, LESSOPEN, PYTHONPATH, RIPGREP_CONFIG_PATH, BASH_ENV …) is the
# losing game this hook already stopped playing for verbs.
_SAFE_ENV = re.compile(r"^(?:LC_[A-Z_]+|LANG|LANGUAGE|TZ|NO_COLOR|CLICOLOR|CLICOLOR_FORCE"
                       r"|COLUMNS|LINES|TERM|COLORTERM|POSIXLY_CORRECT"
                       r"|PYTHONDONTWRITEBYTECODE|PYTHONUNBUFFERED|PYTHONIOENCODING)$")


def unsafe_env(scan: dict) -> list:
    """The assigned names in a scanned command that are not locale/display-only."""
    return [n for n in scan.get("env") or [] if not _SAFE_ENV.match(n)]


def _git_is_read_only(args: list):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        # Found in the FACTORY-175 review: git's global options can INJECT a program.
        # `-c core.fsmonitor=<prog>` runs it on `status`, `-c diff.external=<prog>` on
        # `diff`, `--config-env` is the same through a variable, and `--exec-path=<dir>`
        # moves where git looks for its helpers. All measured writing, all allowed.
        if a == "-c" or a == "--config-env" or a.startswith("--config-env="):
            return False, (f"`git {a}` sets configuration, and configuration can name a "
                           "program git runs (core.fsmonitor, diff.external, core.pager)")
        if a.startswith("--exec-path="):
            return False, "`git --exec-path=<dir>` runs git's helpers from that directory"
        if a in ("-C", "--git-dir", "--work-tree", "--namespace"):
            i += 2
        else:
            i += 1
    if i >= len(args):
        return True, ""                              # bare `git` prints usage
    sub, rest = args[i], args[i + 1:]
    if sub == "grep" and (any(_long_named(t, ("open-files-in-pager",)) for t in rest)
                          or "O" in _short_letters(rest, "efABCm")):
        return False, "`git grep -O/--open-files-in-pager=<prog>` runs that program"
    if sub == "ls-remote" and (any(_long_named(t, ("upload-pack", "exec")) for t in rest)
                               or "-u" in rest):
        return False, "`git ls-remote --upload-pack=<prog>` runs that program"
    if sub == "stash":
        # Bare `git stash` IS `git stash push` — it rewrites the working tree. It sat in
        # the dual list, where "no operands" meant read; only `list`/`show` read.
        if rest and rest[0] in ("list", "show") and not any(
                _long_named(t, ("output",)) for t in rest):
            return True, ""
        return False, "`git stash` without `list`/`show` stashes — it rewrites the tree"
    # FACTORY-175: the diff machinery behind `diff`/`log`/`show`/`whatchanged`/
    # `diff-tree`/`diff-index` takes `--output=<file>` (or `--output <file>`) and
    # WRITES the patch there. Checked for every subcommand: an option a subcommand
    # does not know is an error, never a read. `--output-indicator-*` is display-only.
    if any(t == "--output" or t.startswith("--output=") for t in rest):
        return False, "`git … --output=<file>` writes the output to that file"
    if sub in _GIT_READ_SUBCOMMANDS:
        return True, ""
    if sub in _GIT_DUAL_SUBCOMMANDS:
        if all(t in _GIT_DUAL_READ_TOKENS for t in rest):
            return True, ""
        return False, (f"`git {sub}` with operands can write (create/delete/set); only "
                       f"its bare listing forms are read-only")
    return False, f"`git {sub}` is not a read-only subcommand"


# ── reading an argv the way the program will (FACTORY-175) ──────────────────────
# `args` here is the segment's tokens after the verb — redirect tokens included, since
# `_tokens` is a plain split. These helpers skip them: a redirect is governed by
# `_REDIRECT_TARGET`, and counting `> out` as an operand would deny every redirected
# read into the Product.
_REDIR_ONLY = re.compile(r"^[0-9&]*[<>][<>|&]*$")      # `>`, `>>`, `2>`, `<`, `&>`, `<<<`


def _is_redirect_token(tok: str) -> bool:
    return "<" in tok or ">" in tok


def _long_named(tok: str, names) -> bool:
    """True when `--name[=v]` is one of `names` OR AN ABBREVIATION of one: getopt_long
    and git's parse-options both accept any unambiguous prefix (`sort --out=F`,
    `git ls-remote --upload=CMD` — measured), so an exact match is a bypass."""
    if not tok.startswith("--") or len(tok) < 3:
        return False
    name = tok[2:].split("=", 1)[0]
    return bool(name) and any(n.startswith(name) for n in names)


def _short_letters(args, value_letters: str = "") -> set:
    """Every single-letter flag used ANYWHERE in `args`, read the way getopt reads a
    cluster: `-uo F` is -u and -o; in `-to` the `o` is -t's VALUE, not a flag. Scanned
    past operands on purpose — GNU getopt permutes, so `sort IN -o OUT` writes."""
    out, skip = set(), False
    for a in args:
        if skip:
            skip = False
            continue
        if _is_redirect_token(a) or not a.startswith("-") or a.startswith("--") or a == "-":
            continue
        letters = a[1:]
        for j, ch in enumerate(letters):
            out.add(ch)
            if ch in value_letters:
                skip = j == len(letters) - 1      # the value is the NEXT token
                break
    return out


def _operands(args, value_letters: str = "", value_longs=frozenset()) -> list:
    """The positional operands, read the POSIX way: options end at the first operand
    (or `--`), and EVERYTHING after that is an operand. BSD `uniq in.txt -c` writes a
    file named `-c` (measured); counting it as a flag would allow exactly that.
    A GNU tool that permutes reads `-c` as a flag there instead — the union is taken,
    so that form is a false denial, never a missed write."""
    out, i, n, opts_done = [], 0, len(args), False
    while i < n:
        a = args[i]
        if _REDIR_ONLY.match(a):
            i += 2                                # the operator and its target
            continue
        if _is_redirect_token(a):
            i += 1                                # `>out`, `2>/dev/null`, `<in`
            continue
        if opts_done:
            out.append(a)
        elif a == "--":
            opts_done = True
        elif a in value_longs:
            i += 1                                # `-cols 8`, `--skip-fields 2`
        elif a.startswith("-") and a != "-":
            letters = "" if a.startswith("--") else a[1:]
            for j, ch in enumerate(letters):
                if ch in value_letters:
                    if j == len(letters) - 1:
                        i += 1
                    break
        else:
            out.append(a)
            opts_done = True
        i += 1
    return out


_UNIQ_VALUE_LONGS = frozenset({"--skip-fields", "--skip-chars", "--check-chars"})
_XXD_VALUE_LONGS = frozenset({"-cols", "-groupsize", "-len", "-seek", "-name",
                              "-offset"})


def _verb_is_read_only(verb: str, args: list):
    """(ok, why-not). The allowlist, plus the readers that grow a write form.

    FACTORY-175: every verb on `_READ_ONLY_VERBS` was reviewed for an output-file
    operand or flag. The ones that have one are refused HERE, by reading the argv the
    way the program does; the review itself is pinned in
    `tests/gates/test_agent_hook_output_operands.py`."""
    if not verb or verb in _SHELL_KEYWORDS:
        return True, ""
    if verb == "git":
        return _git_is_read_only(args)
    if verb not in _READ_ONLY_VERBS:
        return False, (f"`{verb}` is not on the read-only allowlist — every "
                       "interpreter and every unrecognised verb can write")
    if verb == "find" and any(a in _FIND_WRITE_FLAGS for a in args):
        return False, "`find` with -delete/-exec writes"
    if verb == "sort" and ({"o", "T"} & _short_letters(args, "kotTS")
                           or any(_long_named(a, ("output", "temporary-directory",
                                                  "compress-program")) for a in args)):
        return False, ("`sort -o/--output` writes its output file (and -T / "
                       "--compress-program write or run elsewhere)")
    if verb in ("tail", "head") and "-o" in args:
        return False, f"`{verb} -o` writes"
    if verb == "uniq":
        ops = [o for o in _operands(args, "fsw", _UNIQ_VALUE_LONGS)
               if not re.match(r"^\+\d+$", o)]            # BSD's obsolete `+N` skip
        if len(ops) >= 2:
            return False, "`uniq IN OUT` writes its second operand"
    if verb == "xxd" and len(_operands(args, "cglsonR", _XXD_VALUE_LONGS)) >= 2:
        return False, "`xxd IN OUT` writes its second operand"
    if verb == "tree" and ({"o", "R"} & _short_letters(args)
                           or any(_long_named(a, ("output",)) for a in args)):
        return False, "`tree -o FILE` writes the listing (and -R writes 00Tree.html)"
    if verb == "file" and ("C" in _short_letters(args, "efFmP")
                           or any(_long_named(a, ("compile",)) for a in args)):
        return False, "`file -C/--compile` writes a compiled magic file into the cwd"
    # The other class the review found: a reader that RUNS a program on request.
    if verb == "fd" and ({"x", "X"} & _short_letters(args, "dEteScjoxX")
                         or any(_long_named(a, ("exec", "exec-batch")) for a in args)):
        return False, "`fd -x/-X/--exec` runs a program for each match"
    if verb == "rg" and any(_long_named(a, ("pre", "hostname-bin")) for a in args):
        return False, "`rg --pre/--hostname-bin <prog>` runs that program"
    if verb in ("ag", "ack", "delta") and any(_long_named(a, ("pager",)) for a in args):
        return False, f"`{verb} --pager=<prog>` runs that program"
    return True, ""


LAUNCHER_REL = os.path.join("_SYSTEM", "tools", "factory_launch.py")


# `python3`, `python`, and versioned CPython basenames like `python3.14` — a
# versioned name is still just CPython, and every other rule below still applies to
# it. Denying it would be the pass-3 failure again: closing the hole by breaking the
# door on a machine whose interpreter happens to carry its minor version.
_PY_INTERPRETERS = frozenset(
    ["python", "python3"] + [f"python3.{n}" for n in range(6, 30)])


def _is_the_launcher(scan, scope, base, command=""):
    """True when the command is the Factory's OWN sanctioned entry point.

    THE REGRESSION THIS FIXES. `python3` is deliberately absent from
    `_READ_ONLY_VERBS` — any interpreter can write, and enumerating safe ones is a
    losing game. But that made this hook deny the one command a bound Product session
    exists to run:

        python3 ../CW-Factory/_SYSTEM/tools/factory_launch.py bind --product .

    which is verbatim `_SYSTEM/templates/PRODUCT_CLAUDE.thin.md:61` and the
    `gen-bootstrap` block. `bind`, `run`, `verify`, even `--help` were all refused, so
    a bound Product could not run ANY Factory tool. The first bind appeared to work
    only because the hook does not exist until that bind installs it. 72 hook tests
    passed throughout: none of them invoked the launcher.

    The exemption is deliberately narrow, and it is a PATH match, not a name match:

      * the script argument must RESOLVE to `<factory_root>/_SYSTEM/tools/
        factory_launch.py` — a Product-authored `./factory_launch.py`, or a copy under
        any other root, does not qualify;
      * a redirect anywhere in the command still denies, before this is consulted;
      * every other segment must still pass the read-only allowlist, so
        `python3 …/factory_launch.py bind && rm -rf <factory>` is refused on the
        second segment.

    What this exemption does NOT do is vouch for what the launcher then executes. It
    says only "this is the sanctioned door". The launcher's own gates decide what
    comes through it, and a forged binding record is their problem, not this hook's.
    """
    verbs = scan.get("verbs") or []
    if len(verbs) != 1:
        return False                       # no chaining through the sanctioned door
    verb, args = verbs[0]
    if verb not in _PY_INTERPRETERS:
        return False

    # The segment's FIRST token must BE the interpreter — no env assignment, no
    # wrapper, nothing ahead of it.
    #
    # An env prefix turns the exemption into arbitrary code: `_verb_of` deliberately
    # SKIPS `VAR=value` to find the real verb, so prefixes are invisible in `args`,
    # and `PYTHONPATH=<product>/evil python3 <launcher>` runs the Product's
    # `sitecustomize.py` at interpreter startup, before the launcher's first line.
    #
    # My first attempt matched `^VAR=` against the raw command, and I caught it
    # bypassed before a critic did: `env` is in `_WRAPPERS`, so
    # `env PYTHONPATH=… python3 <launcher>` puts the assignment past the anchor and
    # `_verb_of` unwraps back to `python3`. Enumerating the ways to get a variable in
    # front of an interpreter is the same losing game as enumerating interpreters —
    # which is what this whole hook stopped doing. So: the documented command starts
    # with `python3`, and the exemption covers exactly that shape.
    #
    # The cost is honest false denials on forms nobody documents: `env python3 …`,
    # `exec python3 …`, `sudo python3 …`. Each is one word away from the sanctioned
    # command and the refusal names it.
    toks = _tokens((command or "").strip())
    if not toks or os.path.basename(toks[0].lstrip("({")) not in _PY_INTERPRETERS:
        return False

    # The launcher must be the token PYTHON ACTUALLY EXECUTES — i.e. the FIRST
    # argument, with no interpreter flag ahead of it. `python3 -c CODE <launcher>`
    # and `python3 -m evilmod <launcher>` both name the launcher and never run it:
    # it is a decoy positional argument while `-c`/`-m` take the interpreter. Both
    # were ALLOWED before this check, and both wrote into the Factory.
    #
    # Deliberately stricter than "reject -c and -m": ANY leading flag disqualifies.
    # `-S`, `-E` and `-I` each disable the startup hooks documented in
    # sitecustomize.py's HONEST LIMITS, and the sanctioned invocation — verbatim in
    # PRODUCT_CLAUDE.thin.md — carries no interpreter flags at all. An exemption on a
    # security boundary should cover exactly the documented command and nothing more.
    if not args or args[0].startswith("-"):
        return False
    script = args[0]
    resolved = _norm(script) if os.path.isabs(os.path.expanduser(script)) else (
        _norm(script, base=base) if base else "")
    if not resolved:
        return False
    for root in scope.get("factory_roots") or [scope.get("factory_root")]:
        if root and resolved == _norm(os.path.join(root, LAUNCHER_REL)):
            return True
    return False


def _cd_target(args: list, running: str) -> str:
    """The working directory after a `cd`. '' means UNKNOWN, which makes any later
    relative path unresolvable — and an unresolvable path denies."""
    operand = next((a for a in args if not a.startswith("-")), None)
    if operand is None:
        return _norm(os.path.expanduser("~"))
    if operand == "-" or "$" in operand:
        return ""
    if os.path.isabs(os.path.expanduser(operand)):
        return _norm(operand)
    return _norm(operand, base=running) if running else ""


def scan_bash(command: str, cwd: str, scope: dict) -> dict:
    """Resolve every path a command names, threading `cd` through the segments."""
    touches, unresolved, verbs, bad_redirect = set(), [], [], []
    hardlinks, env_names = [], []
    running = cwd

    def note(path_str, resolved):
        if resolved:
            kind = _classify(resolved, scope)
            if kind not in ("factory", "other") and _laundered_hardlink(resolved, scope):
                # D3: a second name for a file on a protected volume. Classified as
                # `factory` so the EXISTING policy governs it — a read through the
                # link is still fine, a write is not.
                hardlinks.append(path_str)
                kind = "factory"
            touches.add(kind)
        else:
            unresolved.append(path_str)

    # R2: a token whose value we cannot know is UNRESOLVED, never "relative to cwd".
    #
    # `resolve("$F/pwn")` used to fall through to the relative branch and be _norm'd
    # into `<product>/$F/pwn` — classified `product`, allowed. So:
    #
    #     F=<factory>; echo x > $F/pwn          -> ALLOW, and the write LANDED
    #     F=<factory>; printf y >> $F/README.md -> ALLOW
    #
    # while the docstring's HONEST LIMITS claimed an assignment spelled out in the
    # same command IS caught. That was true for `rm $F/x` (a write verb) and false for
    # every redirect. Worse, the second net had already SEEN the Factory in that
    # command (`_root_mentioned` → touches={"factory"}) and the hook allowed the write
    # anyway. `sitecustomize` is not on this path — `echo` is not Python.
    #
    # Returning "" routes the token into `unresolved` / `bad_redirect`, where the
    # existing rule already refuses: an unresolvable path is denied, never guessed.
    # Cost: a legitimate `$HOME/notes.txt` inside the Product now denies too. That is
    # the same trade the rest of this hook makes, and the refusal names the remedy.
    _UNKNOWABLE = ("$", "`")

    def resolve(raw):
        raw = raw.strip("'\"")
        if not raw:
            return ""
        if any(ch in raw for ch in _UNKNOWABLE):
            return ""                            # value is not knowable from the text
        if os.path.isabs(os.path.expanduser(raw)):
            return _norm(raw)
        return _norm(raw, base=running) if running else ""

    # A HEREDOC BODY IS DATA FOR THE COMMAND'S STDIN, NOT SHELL (S174). Parsed as shell, a
    # Python body's `'<no id>'` or `a > b` became an unparseable redirect and the whole
    # command was refused. So the SHELL structure (segments, verbs, redirects, `cd`) is
    # read from the command with every body cut out — and every path-shaped token in a
    # body is still resolved and classified below, so `python3 - <<EOF open('<root>/x',
    # 'w') EOF` touches that root exactly as before. The `_root_mentioned` second net
    # also still reads the FULL command.
    bodies = []

    def _cut_heredoc(m):
        bodies.append(m.group(3))
        return m.group(0).split("\n", 1)[0]

    shell_text = _HEREDOC.sub(_cut_heredoc, command)

    for segment in _split_segments(_AMP_FILE.sub("> ", _FD_DUP.sub(" ", shell_text))):
        segment = segment.strip()
        if not segment:
            continue
        toks = _tokens(segment)
        verb, args = _verb_of(toks)
        env_names.extend(_env_assignments(toks))

        for cand in _PATHISH.findall(segment):
            if "/" not in cand:
                continue
            note(cand, resolve(cand))

        quoted = _quoted_spans(segment)
        for m in _REDIRECT_TARGET.finditer(segment):
            if any(a < m.start() < b for a, b in quoted):
                continue                     # a `>` inside quotes is data, not a redirect
            target = (m.group(1) or "").strip("'\"")
            if not target:
                bad_redirect.append("<unparseable redirect target>")
                continue
            resolved = resolve(target)
            if not resolved:
                bad_redirect.append(target)          # cannot prove where it lands
            elif _classify(resolved, scope) in ("factory", "other"):
                bad_redirect.append(target)
            elif _laundered_hardlink(resolved, scope):
                hardlinks.append(target)             # D3, see `_laundered_hardlink`
                bad_redirect.append(target)

        if verb:
            verbs.append((verb, args))
        if verb == "cd":
            running = _cd_target(args, running)
            if running:
                touches.add(_classify(running, scope))
            else:
                unresolved.append("cd to an unresolvable directory")

    for body in bodies:
        for cand in _PATHISH.findall(body):
            if "/" in cand and not any(ch in cand for ch in _UNKNOWABLE):
                resolved = resolve(cand)
                if resolved:
                    touches.add(_classify(resolved, scope))

    # second net: an absolute root embedded in a token shape the tokeniser missed.
    # Product-root occurrences are blanked first so a nested Product does not read as
    # a Factory mention.
    scrubbed = command
    prod = scope["product_root"]
    if prod:
        low = scrubbed.lower()
        i = low.find(prod.lower())
        while i >= 0:
            scrubbed = scrubbed[:i] + ("\x00" * len(prod)) + scrubbed[i + len(prod):]
            low = scrubbed.lower()
            i = low.find(prod.lower())
    for root in scope["other_roots"]:
        if _root_mentioned(command, root):
            touches.add("other")
    for root in scope["factory_roots"]:
        if _root_mentioned(scrubbed, root):
            touches.add("factory")

    touches.discard("")
    return {"touches": touches, "unresolved": unresolved, "verbs": verbs,
            "bad_redirect": bad_redirect, "hardlinks": hardlinks, "env": env_names}


def decide(tool_name: str, tool_input: dict, scope: dict, cwd=None):
    """-> (decision, reason) where decision is "allow" or "deny"."""
    product = scope["product_root"]
    factory = scope["factory_root"]
    degraded = scope.get("unresolved") or []
    base = cwd if (cwd and os.path.isabs(cwd)) else ""

    def deny(rule, detail):
        return "deny", (f"{DENY_MARKER} rule={rule} tool={tool_name} {detail} — "
                        f"{CONTRACT_CITE}")

    def degraded_deny(what):
        return deny("scope-unresolved",
                    f"{DEGRADED_MARKER}: the other-Product denylist could not be built "
                    f"({'; '.join(degraded)}), so {what} cannot be proven in scope. "
                    "Fix the registry entry in the Factory (make repo.path absolute, "
                    "or check out / unregister the Product) and re-bind. Work confined "
                    "to the bound Product is still allowed.")

    if tool_name == "Bash":
        command = tool_input.get("command") or ""
        if not isinstance(command, str):
            return "allow", ""
        if degraded:
            return degraded_deny("a shell command")
        scan = scan_bash(command, base, scope)
        if "other" in scan["touches"]:
            return deny("bash-other-product",
                        f"command resolves a path under another registered Product "
                        f"({', '.join(scope['other_roots']) or '?'}); a session binds "
                        "exactly one Product")
        if scan["unresolved"]:
            rule = "no-cwd" if not base else "unresolved-path"
            return deny(rule,
                        f"cannot resolve {scan['unresolved'][0]!r}"
                        + ("" if base else " — the PreToolUse payload carried no "
                                           "absolute `cwd`, so a relative path has no "
                                           "anchor")
                        + ". An unresolvable path is refused, never guessed; re-issue "
                          "the command with absolute paths.")
        # An UNRESOLVABLE redirect target denies regardless of what else the command
        # touched — this check used to sit below the early allow, so it only fired when
        # something ELSE in the command had already been recognised as the Factory.
        #
        # `echo x > "$(pwd)/../CW-Factory/pwn"` was allowed by exactly that ordering:
        # the segment splitter cuts on `$(`, the target parses as empty, nothing in the
        # mangled remainder classifies as `factory`, and the function returned allow two
        # branches before reaching here.
        #
        # "I cannot tell where this write lands" is the one case where allowing is
        # indefensible: the whole point is that it MIGHT be the Factory. The cost is
        # real and is the same trade the rest of this hook makes — `> $HOME/notes.txt`,
        # `> ${OUT}/f` and `> $(mktemp)` inside the Product now deny too, and the
        # refusal names the remedy.
        if scan["bad_redirect"]:
            if scan["hardlinks"] and scan["bad_redirect"][0] in scan["hardlinks"]:
                return deny("bash-factory-write",
                            f"redirect target {scan['bad_redirect'][0]!r} is a hard "
                            "link — a regular file with more than one name, on the "
                            "same volume as a protected root. A hard link has no link "
                            "for `realpath` to resolve, so a write through it can land "
                            "under a root this command never names (D3). Write to a "
                            "path with a single name, or `cp` the file first.")
            return deny("bash-factory-write",
                        f"redirect target {scan['bad_redirect'][0]!r} cannot be proven "
                        f"to land outside FACTORY_ROOT {factory!r}. A Product session "
                        "never writes the Factory (A-B2-20), and an unprovable "
                        "destination is refused rather than guessed — re-issue the "
                        "redirect with a literal absolute path.")
        if "factory" not in scan["touches"]:
            return "allow", ""
        # S196 (the FACTORY-175 review): an assignment ahead of a reader can make it run
        # a program — see `_env_assignments`. Checked before the launcher exemption too,
        # which already refuses a prefix on its own line but not `X=v; python3 <launcher>`.
        bad_env = unsafe_env(scan)
        if bad_env:
            return deny("bash-factory-write",
                        f"command touches FACTORY_ROOT {factory!r} and assigns "
                        f"`{bad_env[0]}` — an environment variable can make a reader "
                        "run a program (GIT_CONFIG_*, GIT_EXTERNAL_DIFF, PAGER, "
                        "PYTHONPATH), so the command is not provably a read. Only "
                        "locale/display variables (LC_*, LANG, TZ, NO_COLOR, COLUMNS, "
                        "TERM) may be set here; drop the assignment.")
        if _is_the_launcher(scan, scope, base, command):
            return "allow", ""
        for verb, args in scan["verbs"]:
            ok, why = _verb_is_read_only(verb, args)
            if not ok:
                return deny("bash-factory-write",
                            f"command touches FACTORY_ROOT {factory!r} and is not "
                            f"provably a read: {why}. A Product session never writes "
                            "the Factory (A-B2-20). Reading it IS allowed — use "
                            "cat/head/grep/git show, or copy the file into the Product "
                            "and process it there.")
        if scan["bad_redirect"]:
            return deny("bash-factory-write",
                        f"redirect target {scan['bad_redirect'][0]!r} lands under the "
                        f"Factory (or cannot be resolved); a Product session never "
                        "writes the Factory (A-B2-20)")
        if _INPLACE_EDIT.search(command):
            return deny("bash-factory-write",
                        f"in-place edit under FACTORY_ROOT {factory!r} (A-B2-20)")
        return "allow", ""

    for raw in _tool_paths(tool_name, tool_input):
        if os.path.isabs(os.path.expanduser(raw)):
            p = _norm(raw)
        elif base:
            p = _norm(raw, base=base)
        else:
            return deny("no-cwd",
                        f"path {raw!r} is relative and the PreToolUse payload carried "
                        "no absolute `cwd` to resolve it against. Resolving it against "
                        "the hook process's own directory would be a guess about the "
                        "harness; re-issue with an absolute path.")
        if not p:
            continue
        kind = _classify(p, scope)
        if kind == "other":
            return deny("other-product",
                        f"path {raw!r} is under another registered Product root; a "
                        "session binds exactly one Product")
        # D3 — checked BEFORE the `product` early-continue, because the whole point
        # of a laundered hard link is that the path spelling says `product`.
        if (kind != "factory" and tool_name in WRITE_TOOLS
                and _laundered_hardlink(p, scope)):
            return deny("factory-write",
                        f"path {raw!r} is a hard link — a regular file with more than "
                        "one name, on the same volume as a protected root. A hard link "
                        "has no link for `realpath` to resolve, so a write through it "
                        "can land under a root this path never names (D3). Write to a "
                        "path with a single name, or copy the file first.")
        if kind == "product":
            continue                     # the bound Product always wins
        if kind == "factory" and tool_name in WRITE_TOOLS:
            return deny("factory-write",
                        f"path {raw!r} is under FACTORY_ROOT {factory!r}; a Product "
                        "session never writes the Factory (A-B2-20 / "
                        "SESSION_CONTRACT §1.2). Record it as a Product proposal "
                        "(`Q: Factory`) instead.")
        if degraded and not _under(p, product):
            return degraded_deny(f"path {raw!r}")
    return "allow", ""


# ────────────────────────────────── hook I/O ──────────────────────────────────

def _emit(decision: str, reason: str) -> int:
    """Claude Code `PreToolUse` output. The JSON form is used for BOTH decisions so
    the reason string is always machine-readable; the deny is repeated on stderr
    because that is what a transcript capture greps."""
    payload = {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason or "in scope",
    }}
    sys.stdout.write(json.dumps(payload) + "\n")
    if decision == "deny":
        sys.stderr.write(reason + "\n")
    return 0


def run_hook(stdin_text: str) -> int:
    try:
        payload = json.loads(stdin_text) if stdin_text.strip() else {}
    except ValueError as e:
        sys.stderr.write(f"{ERROR_MARKER}: unparseable PreToolUse payload ({e}) — "
                         "ALLOWING; the agent layer is not guarding this call\n")
        return _emit("allow", f"{ERROR_MARKER}: unparseable payload") if _FAIL_OPEN \
            else _emit("deny", f"{ERROR_MARKER}: unparseable payload")

    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    cwd = payload.get("cwd")
    cwd = _norm(cwd) if isinstance(cwd, str) and os.path.isabs(
        os.path.expanduser(cwd or "")) else ""

    scope, note = load_scope()
    if scope is None:
        sys.stderr.write(f"{INACTIVE_MARKER}: {note} — ALLOWING; the agent-layer scope "
                         "guard is NOT in force for this call\n")
        return _emit("allow", f"{INACTIVE_MARKER}: {note}")

    if tool_name not in WRITE_TOOLS + READ_TOOLS + ("Bash",):
        return _emit("allow", "")

    try:
        decision, reason = decide(tool_name, tool_input, scope, cwd=cwd)
    except Exception as e:  # noqa: BLE001 — see the failure-policy note in the docstring
        sys.stderr.write(f"{ERROR_MARKER}: {type(e).__name__}: {e} — "
                         f"{'ALLOWING' if _FAIL_OPEN else 'DENYING'}\n")
        return _emit("allow" if _FAIL_OPEN else "deny", f"{ERROR_MARKER}: {e}")
    return _emit(decision, reason)


# ──────────────────────────────── selftest ────────────────────────────────────

def _selftest() -> int:
    import subprocess
    import tempfile

    me = os.path.abspath(__file__)  # factory-root: the selftest installs THIS
    # TEMPLATE into a temp Product to test the shipped bytes — not a state root.
    failures = []

    with tempfile.TemporaryDirectory(prefix="pretooluse_selftest_") as td:
        td = os.path.realpath(td)
        factory = os.path.join(td, "CW-Factory")
        product = os.path.join(td, "CW-ProductA")
        other = os.path.join(td, "CW-ProductB")
        hooks = os.path.join(product, ".claude", "hooks")
        reg = os.path.join(factory, "_SYSTEM", "products", "productb")
        mem = os.path.join(product, "_SYSTEM", "_MEMORY")
        for d in (factory, product, other, hooks, reg, mem):
            os.makedirs(d, exist_ok=True)
        Path(factory, "README.md").write_text("factory readme\n")
        Path(factory, "FACTORY.md").write_text("factory contract\n")
        Path(other, "data").mkdir(exist_ok=True)
        Path(other, "data", "deals.json").write_text("{}\n")
        Path(reg, "product.json").write_text(json.dumps(
            {"product_id": "productb", "repo": {"path": other}}))
        Path(mem, "_ACTIVE_SESSION.json").write_text(json.dumps(
            {"product_id": "producta", "product_root": product,
             "factory_root": factory, "binding_token": "t" * 32}))
        installed = os.path.join(hooks, "cw_scope_guard.py")
        Path(installed).write_text(Path(me).read_text())

        def call(tool, tinput, hook=installed, env=None, cwd=product):
            e = {k: v for k, v in os.environ.items() if k != "PRODUCT_ROOT"}
            e["PYTHONDONTWRITEBYTECODE"] = "1"
            e.update(env or {})
            body = {"hook_event_name": "PreToolUse", "tool_name": tool,
                    "tool_input": tinput}
            if cwd is not None:
                body["cwd"] = cwd
            r = subprocess.run(
                [sys.executable, hook], input=json.dumps(body),
                capture_output=True, text=True, env=e, timeout=60)
            try:
                out = json.loads(r.stdout)["hookSpecificOutput"]
            except (ValueError, KeyError) as ex:
                return "BADOUTPUT", f"{ex}: {r.stdout!r} {r.stderr!r}", r
            return out["permissionDecision"], out["permissionDecisionReason"], r

        cases = [
            ("Edit of the Factory README", "Edit",
             {"file_path": os.path.join(factory, "README.md")}, "deny", "factory-write"),
            ("Write into the Factory", "Write",
             {"file_path": os.path.join(factory, "_SYSTEM", "x.json"),
              "content": "x"}, "deny", "factory-write"),
            ("NotebookEdit in the Factory", "NotebookEdit",
             {"notebook_path": os.path.join(factory, "n.ipynb")}, "deny",
             "factory-write"),
            ("Read of FACTORY.md is ALLOWED", "Read",
             {"file_path": os.path.join(factory, "FACTORY.md")}, "allow", None),
            ("Read of another Product", "Read",
             {"file_path": os.path.join(other, "data", "deals.json")}, "deny",
             "other-product"),
            ("Edit inside the bound Product", "Edit",
             {"file_path": os.path.join(product, "PRODUCT.md")}, "allow", None),
            ("Edit of a RELATIVE Factory path", "Edit",
             {"file_path": "../CW-Factory/README.md"}, "deny", "factory-write"),
            ("Edit of a relative in-Product path is ALLOWED", "Edit",
             {"file_path": "./PRODUCT.md"}, "allow", None),
            ("Bash redirect into the Factory", "Bash",
             {"command": f"echo hi > {factory}/README.md"}, "deny",
             "bash-factory-write"),
            ("Bash rm in the Factory", "Bash",
             {"command": f"rm -rf {factory}/_SYSTEM/_MEMORY"}, "deny",
             "bash-factory-write"),
            ("Bash cat of the Factory is ALLOWED", "Bash",
             {"command": f"cat {factory}/FACTORY.md"}, "allow", None),
            ("Bash git log in the Factory is ALLOWED", "Bash",
             {"command": f"git -C {factory} log --oneline -5"}, "allow", None),
            ("Bash git commit in the Factory", "Bash",
             {"command": f"git -C {factory} commit -am wip"}, "deny",
             "bash-factory-write"),
            ("Bash touching another Product at all", "Bash",
             {"command": f"ls {other}/data"}, "deny", "bash-other-product"),
            ("Bash sed -i into the Factory", "Bash",
             {"command": f"sed -i '' s/a/b/ {factory}/README.md"}, "deny",
             "bash-factory-write"),
            ("Bash writing inside the Product", "Bash",
             {"command": f"echo hi > {product}/notes.txt"}, "allow", None),
            ("python3 -c open(factory)", "Bash",
             {"command": f"python3 -c \"open('{factory}/pwn.txt','w')\""}, "deny",
             "bash-factory-write"),
            ("python3 --out into the Factory", "Bash",
             {"command": f"python3 gen.py --out {factory}/x.json"}, "deny",
             "bash-factory-write"),
            ("node -e writeFileSync", "Bash",
             {"command": f"node -e \"require('fs').writeFileSync('{factory}/x','y')\""},
             "deny", "bash-factory-write"),
            ("sqlite3 against a Factory DB", "Bash",
             {"command": f"sqlite3 {factory}/_SYSTEM/_KB/sa_state.db "
                         "'delete from lessons'"}, "deny", "bash-factory-write"),
            ("cd into the Factory then write", "Bash",
             {"command": "cd ../CW-Factory && echo planted > README.md"}, "deny",
             "bash-factory-write"),
            ("two-step cd into the Factory then rm", "Bash",
             {"command": "cd .. && cd CW-Factory && rm README.md"}, "deny",
             "bash-factory-write"),
            ("cd into the Factory then cat is ALLOWED", "Bash",
             {"command": "cd ../CW-Factory && cat FACTORY.md"}, "allow", None),
            # R2 — a Factory write behind a same-command shell variable. Every one of
            # these was ALLOWED before 2026-08-20, and the first one's byte LANDED:
            # `resolve("$F/pwn")` is not absolute, so it was normalised against cwd
            # into `<product>/$F/pwn`, classified `product`, and never reached the
            # redirect check. No case in this table used a `$VAR`, which is why 26
            # green decisions said nothing about it.
            # 🔴-1 — the sanctioned entry point. Every one of these was DENIED after
            # the interpreter tightening, which meant a bound Product session could not
            # run a single Factory tool. The last two are the guard rails on the
            # exemption: it is a PATH match against <factory>/_SYSTEM/tools/, and it
            # does not open a door for a second command chained behind it.
            ("the launcher itself is ALLOWED (relative, as the thin CLAUDE.md spells it)",
             "Bash", {"command": "python3 ../CW-Factory/_SYSTEM/tools/factory_launch.py "
                                 "bind --product ."}, "allow", None),
            ("the launcher itself is ALLOWED (absolute)", "Bash",
             {"command": f"python3 {factory}/_SYSTEM/tools/factory_launch.py verify"},
             "allow", None),
            ("the launcher's --help is ALLOWED", "Bash",
             {"command": f"python3 {factory}/_SYSTEM/tools/factory_launch.py --help"},
             "allow", None),
            ("launcher run dispatching a Factory tool is ALLOWED", "Bash",
             {"command": f"python3 {factory}/_SYSTEM/tools/factory_launch.py run "
                         "--product . open_items_tool.py list"}, "allow", None),
            # A Product running its OWN script against its OWN tree is fine and is
            # allowed earlier, before the exemption is consulted — the hook has no
            # business blocking a Product from executing Product code. The guard rail
            # that matters is that a Product-authored copy cannot be used to REACH the
            # Factory: same basename, wrong path, and the exemption does not apply.
            # 🔴-A — the four forms that turned the launcher exemption into arbitrary
            # code. Every one was ALLOWED by the first version of the exemption, and
            # every one landed bytes in the Factory when run for real. The first two
            # never execute the launcher at all: it is a decoy positional argument
            # while -c / -m take the interpreter. The last two run Product code at
            # interpreter startup, BEFORE the launcher's first line.
            ("-c with the launcher as a decoy argument", "Bash",
             {"command": f"python3 -c \"open('{factory}/pwn','w')\" "
                         f"{factory}/_SYSTEM/tools/factory_launch.py"},
             "deny", "bash-factory-write"),
            ("-m runs a Product module, not the launcher", "Bash",
             {"command": f"python3 -m evilmod {factory}/_SYSTEM/tools/factory_launch.py"},
             "deny", "bash-factory-write"),
            ("a PYTHONPATH prefix runs Product sitecustomize first", "Bash",
             {"command": f"PYTHONPATH={product}/evil python3 "
                         f"{factory}/_SYSTEM/tools/factory_launch.py verify"},
             "deny", "bash-factory-write"),
            ("a PYTHONSTARTUP prefix is the same shape", "Bash",
             {"command": f"PYTHONSTARTUP={product}/evil.py python3 "
                         f"{factory}/_SYSTEM/tools/factory_launch.py verify"},
             "deny", "bash-factory-write"),
            ("-S disables the startup hooks and is not the documented command", "Bash",
             {"command": f"python3 -S {factory}/_SYSTEM/tools/factory_launch.py verify"},
             "deny", "bash-factory-write"),
            # The `env` WRAPPER puts the assignment past a start-of-string anchor, and
            # `_verb_of` unwraps it straight back to `python3`. My first fix for the
            # env-prefix class matched `^VAR=` and these two walked through it. Hence
            # the rule that the segment's FIRST token must BE the interpreter.
            ("env WRAPPER carrying the override gate", "Bash",
             {"command": f"env CW_LAUNCHER_ALLOW_ROOT_OVERRIDE=1 python3 "
                         f"{factory}/_SYSTEM/tools/factory_launch.py run --product ."},
             "deny", "bash-factory-write"),
            ("env WRAPPER carrying PYTHONPATH", "Bash",
             {"command": f"env PYTHONPATH={product}/evil python3 "
                         f"{factory}/_SYSTEM/tools/factory_launch.py verify"},
             "deny", "bash-factory-write"),
            ("exec wrapper is not the documented command", "Bash",
             {"command": f"exec python3 {factory}/_SYSTEM/tools/factory_launch.py verify"},
             "deny", "bash-factory-write"),
            # …and the counter-case, so the rule is not simply "deny more": a versioned
            # CPython basename is still CPython and every other rule still applies.
            ("a versioned python3.N still reaches the launcher", "Bash",
             {"command": f"python3.14 {factory}/_SYSTEM/tools/factory_launch.py verify"},
             "allow", None),
            ("a PRODUCT-authored factory_launch.py cannot reach the Factory", "Bash",
             {"command": f"python3 {product}/factory_launch.py --factory-root {factory} "
                         "bind --product ."}, "deny", "bash-factory-write"),
            ("the exemption does not carry a chained command", "Bash",
             {"command": f"python3 {factory}/_SYSTEM/tools/factory_launch.py verify "
                         f"&& rm -rf {factory}/_SYSTEM"}, "deny", "bash-factory-write"),
            ("a redirect still denies even through the launcher", "Bash",
             {"command": f"python3 {factory}/_SYSTEM/tools/factory_launch.py verify "
                         f"> {factory}/out.txt"}, "deny", "bash-factory-write"),
            ("$VAR redirect into the Factory (absolute)", "Bash",
             {"command": f"F={factory}; echo x > $F/pwn"}, "deny", "bash-factory-write"),
            ("$VAR redirect into the Factory (relative)", "Bash",
             {"command": "F=../CW-Factory; echo x > $F/pwn"}, "deny", "bash-factory-write"),
            ("$VAR append into the Factory", "Bash",
             {"command": f"F={factory}; printf y >> $F/README.md"}, "deny", "bash-factory-write"),
            ("$VAR redirect fed by a Product read", "Bash",
             {"command": f"F={factory}; cat README.md > $F/pwn"}, "deny", "bash-factory-write"),
            ("command substitution into the Factory", "Bash",
             {"command": "echo x > \"$(pwd)/../CW-Factory/pwn\""}, "deny", "bash-factory-write"),
            ("relative cat of another Product", "Bash",
             {"command": "cat ../CW-ProductB/data/deals.json"}, "deny",
             "bash-other-product"),
            ("copy OUT of the Product INTO the Factory", "Bash",
             {"command": f"cp {product}/notes.txt {factory}/notes.txt"}, "deny",
             "bash-factory-write"),
            ("an unmatched tool is untouched", "Glob",
             {"pattern": "**/*.py"}, "allow", None),
        ]
        for name, tool, tinput, want, rule in cases:
            got, reason, r = call(tool, tinput)
            if got != want:
                failures.append(f"{name}: {got} (want {want}) — {reason} "
                                f"| stderr {r.stderr.strip()[:200]}")
                continue
            if want == "deny":
                if DENY_MARKER not in reason or f"rule={rule}" not in reason:
                    failures.append(f"{name}: reason not greppable: {reason!r}")
                if DENY_MARKER not in r.stderr:
                    failures.append(f"{name}: deny absent from stderr (the soak greps "
                                    f"stderr): {r.stderr.strip()[:200]}")

        # a payload with no `cwd` still classifies ABSOLUTE paths…
        got, _reason, _r = call("Edit", {"file_path": os.path.join(factory, "README.md")},
                                cwd=None)
        if got != "deny":
            failures.append(f"no-cwd absolute Edit: {got} (want deny)")
        # …and REFUSES a relative one rather than guessing an anchor
        got, reason, _r = call("Edit", {"file_path": "../CW-Factory/README.md"},
                               cwd=None)
        if got != "deny" or "rule=no-cwd" not in reason:
            failures.append(f"no-cwd relative Edit: {got} / {reason!r} — expected a "
                            "deny with rule=no-cwd")

        # a ROLLBACK runtime: the binding record names `.runtime/rollback-<date>`, and
        # a relative repo.path must still resolve against the CANONICAL checkout.
        runtime = os.path.join(factory, ".runtime", "rollback-2026-08-20")
        os.makedirs(os.path.join(runtime, "_SYSTEM", "products"), exist_ok=True)
        Path(runtime, "FACTORY.md").write_text("materialised runtime\n")
        Path(reg, "product.json").write_text(json.dumps(
            {"product_id": "productb", "repo": {"path": "../CW-ProductB"}}))
        Path(mem, "_ACTIVE_SESSION.json").write_text(json.dumps(
            {"product_id": "producta", "product_root": product,
             "factory_root": runtime, "binding_token": "t" * 32}))
        got, reason, _r = call("Read",
                               {"file_path": os.path.join(other, "data", "deals.json")})
        if got != "deny" or "rule=other-product" not in reason:
            failures.append(f"rollback runtime: other-Product Read got {got} "
                            f"({reason!r}) — the denylist resolved against the runtime "
                            "instead of the canonical checkout")
        got, reason, _r = call("Edit", {"file_path": os.path.join(factory, "README.md")})
        if got != "deny":
            failures.append("rollback runtime: the CANONICAL Factory was writable "
                            f"({got} / {reason!r})")

        # an unresolvable registered Product -> DEGRADED: refuse, never a short denylist
        Path(reg, "product.json").write_text(json.dumps(
            {"product_id": "productb", "repo": {"path": "../CW-NotCheckedOut"}}))
        Path(mem, "_ACTIVE_SESSION.json").write_text(json.dumps(
            {"product_id": "producta", "product_root": product,
             "factory_root": factory, "binding_token": "t" * 32}))
        got, reason, _r = call("Read", {"file_path": os.path.join(factory, "FACTORY.md")})
        if got != "deny" or "rule=scope-unresolved" not in reason:
            failures.append(f"degraded scope: {got} / {reason!r} — an unbuildable "
                            "denylist must refuse, not allow")
        got, reason, _r = call("Write", {"file_path": os.path.join(product, "x.md"),
                                         "content": "x"})
        if got != "allow":
            failures.append(f"degraded scope: work inside the bound Product must still "
                            f"be allowed, got {got} / {reason!r}")

        # unbound: no binding record -> INACTIVE, allow, and LOUD about it
        Path(reg, "product.json").write_text(json.dumps(
            {"product_id": "productb", "repo": {"path": other}}))
        os.remove(os.path.join(mem, "_ACTIVE_SESSION.json"))
        got, reason, r = call("Edit", {"file_path": os.path.join(factory, "README.md")})
        if got != "allow" or INACTIVE_MARKER not in r.stderr:
            failures.append(f"unbound: {got} / stderr {r.stderr.strip()[:200]} — "
                            "expected allow + a loud INACTIVE marker")

        # corrupt binding record -> INACTIVE, allow, loud (never a silent pass)
        Path(mem, "_ACTIVE_SESSION.json").write_text("{ not json")
        got, reason, r = call("Edit", {"file_path": os.path.join(factory, "README.md")})
        if got != "allow" or INACTIVE_MARKER not in r.stderr:
            failures.append(f"corrupt record: {got} / stderr {r.stderr.strip()[:200]}")

    if failures:
        for f in failures:
            sys.stderr.write(f"✗ {f}\n")
        return 1
    print("✓ pretooluse_scope_hook selftest passed (47 decisions + cwd, rollback, "
          "degraded and inactive cases)")
    return 0


def _explain() -> int:
    scope, note = load_scope()
    if scope is None:
        print(f"{INACTIVE_MARKER}: {note}")
        return 1
    print(f"binding record : {scope['record']}")
    print(f"product_root   : {scope['product_root']}   (writes allowed)")
    for r in scope["factory_roots"]:
        print(f"factory_root   : {r}   (READ allowed, WRITE denied)")
    for r in scope["other_roots"]:
        print(f"other Product  : {r}   (all access denied)")
    if not scope["other_roots"]:
        print("other Product  : none registered")
    if scope["unresolved"]:
        for u in scope["unresolved"]:
            print(f"{DEGRADED_MARKER}: {u}")
        print("the denylist is INCOMPLETE — every call outside the bound Product is "
              "REFUSED until the registry is fixed")
        return 1
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "selftest":
        raise SystemExit(_selftest())
    if arg == "explain":
        raise SystemExit(_explain())
    raise SystemExit(run_hook(sys.stdin.read()))
