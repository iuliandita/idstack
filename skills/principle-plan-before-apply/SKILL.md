---
name: principle-plan-before-apply
description: "Apply before any state-mutating command (apply, sync, upgrade, Ansible without --check, DNS or firewall change). Its only input is a reviewed artifact from a read-only step: a saved plan, a rendered diff, check-mode output."
disable-model-invocation: true
---

# Plan Before Apply

The only input to a state-mutating command is an artifact a read-only step produced and someone reviewed: a saved plan file, a rendered diff against live, check-mode output. Apply exactly that artifact, nothing recomputed in between.

**Why:** a command that plans and applies in one step decides what to do at the moment it runs, against whatever state exists then. If state moved since you looked (another apply, a restored state file, a merged PR), it does something nobody reviewed. Reviewing a plan and then running a fresh `apply` is reviewing one thing and running another.

**The idea:** split every change into a read-only step that produces a reviewable artifact and a write step that consumes it. Save the artifact to a file. Review the file, not a terminal scroll. When anything touches the target after the artifact was made, the artifact is stale: produce it again and review again. Never reuse a plan after another apply to the same state.

Tools that cannot consume a saved artifact (Ansible, `kubectl apply`, appliances) still follow the split: check mode or a server-side diff first, reviewed, then the write with the same inputs, then a second check that shows no remaining changes.

**The test:**
1. Can you name the file this write consumes, and when it was produced?
2. Has anything touched the target since then?
3. After the write, does a fresh read-only pass show no remaining changes?

If you cannot answer the first two, the write is not ready.
