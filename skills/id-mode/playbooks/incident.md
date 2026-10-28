### Incident

**You own the timeline. Mitigate first, root-cause second.**

For user-visible impact that needs coordination: declare, mitigate, communicate, learn. The agent never sends a message. It drafts them, and sending is a gate.

1. Pin the target per `references/targets.md`. Confirm VPN and access before reading a failure as a fault.
2. Declare. State impact in user terms, severity from impact, and the start time (UTC). Open the timeline file per `references/evidence.md`.
3. Run `live-diagnosis` for the cause, in parallel with mitigation.
4. **Gate:** each mitigation (rollback, failover, scale, restart). After it, hold the symptom query below its threshold for an agreed period before calling the incident mitigated. Log each gate and answer.
5. Draft, never send: a technical update, a short non-technical summary, and an external message for customers or vendors when needed. Use numbers over adjectives. Do not overstate what was done or verified. Label each claim verified or inferred.
   Jev decision point (optional): per claim in a draft message, ask "supported by the evidence?". Any claim below 0.7 is flagged for rewording before the operator sends. Jev never clears a draft.
6. Have a second model from another family check external drafts against the timeline.
7. **Gate:** sending any message. Show the final text and the recipients, then stop. Approval covers that text only.
8. Write a postmortem when the trigger is met (user-visible downtime, data loss, manual intervention, monitoring missed it). Cover impact, timeline, contributing causes, what went well, and action items.
9. Every action item becomes a tracked issue with an owner.

Never: send, post, or page on your own, or call an incident mitigated on a green dashboard alone.

Calls: **debug-triage**, **observability**.
Principles: pin-the-target, fix-root-causes, encode-lessons-in-structure.

**Reply:** incident state, timeline summary, mitigations with evidence, drafts, issues filed.
