---
name: principle-pin-the-target
description: "Apply before the first command against any live system (cluster, cloud account, workspace, host, zone). Name the target, check it matches the task, and pass it explicitly on every command."
disable-model-invocation: true
---

# Pin the Target

Name the system you are about to touch, check it is the one the task means, and pass it explicitly on every command. An implicit default (the current kube context, the default cloud profile, the selected workspace) is a bug waiting for the wrong terminal.

**Why:** the same command against the wrong target is the most common way a correct change becomes an outage. Defaults are shared state: another shell, a script, or a previous task can change them between two of your commands, and nothing in the command's output tells you.

**The idea:** read the target once, from the tool itself (`kubectl config current-context`, `aws sts get-caller-identity`, the backend and workspace, `hostname` over SSH). Compare it to the task's named environment. Record it. From then on, put it on every command line (`--context`, `--profile`, `-chdir`, `--limit`), so each command is correct on its own and a log line shows where it ran. Keep unrelated estates (work and personal, two customers) out of the same session.

**The test:**
1. Does every command against a live system name its target on the command line?
2. Was the target read from the tool and checked against the task, not assumed?
3. Would this command still hit the right system if someone changed the default in another shell?
