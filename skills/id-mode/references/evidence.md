# Evidence and the reply

## Evidence log

Keep a decision trail with pstack's **show-me-your-work** skill for any playbook that touches a live system or runs longer than a few steps. Add to it:

- **Timeline.** One line per command or observation, UTC timestamp first, target named.
- **Artifacts.** Paths to saved plan files, renders, check-mode output, and query results, with when each was produced. An artifact older than the last change to its target is stale.
- **Gates.** Each gate block shown, the operator's answer verbatim, and the turn it came in.
- **Grant checks.** The predicate, the command that checked it, and its output.

The log stays local unless the operator asks to commit it. It holds hostnames and command output, so never commit it to a public repo, and redact secrets, tokens, and internal addresses before quoting it anywhere shared.

## Labels

Every claim in the reply carries one label in the same sentence:

- **verified:** you ran the check this session and quote or cite its output.
- **inferred:** follows from verified facts, with the reasoning named.
- **guess:** a prediction or an unseen cause.

A proxy (CI green, "Synced/Healthy", a merged PR, a job's exit code) never makes a claim about live state verified on its own.

## Reply sections

After pstack's Writing the reply and the playbook's own Reply line, every idstack reply carries:

- **Target.** What was pinned, and how you checked it.
- **State now.** The current state of the target, not a narrative of what you did.
- **Evidence.** The checks behind each claim, labeled.
- **Held.** Each gate not passed, and what it needs (an approval, a fresh plan, a soak period).
- **Next.** The one or two actions that move it forward, and who owns each.
