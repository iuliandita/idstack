// idstack guard for OpenCode 2.x. All decisions come from `idstack guard hook --harness opencode`;
// this file only forwards each shell call and throws (which blocks the call) on a deny.
import { execFile } from "node:child_process"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const CLI = resolve(dirname(fileURLToPath(import.meta.url)), "../../../bin/idstack")
const SHELL_TOOLS = new Set(["shell", "bash"])

function hook(command, cwd) {
  return new Promise((done, fail) => {
    const child = execFile(CLI, ["guard", "hook", "--harness", "opencode"], { cwd, timeout: 15000 }, (err, stdout) => {
      if (err) return fail(err)
      done(stdout.trim())
    })
    child.stdin.end(JSON.stringify({ tool_name: "bash", tool_input: { command } }))
  })
}

async function setup(ctx) {
  await ctx.tool.hook("execute.before", async (event) => {
    if (!SHELL_TOOLS.has(String(event.tool).toLowerCase())) return
    const input = event.input
    const command = input?.command
    if (command === "") return
    // A list is joined by the CLI; any other shape is held, since it cannot be checked.
    const readable = typeof command === "string" || (Array.isArray(command) && command.every((c) => typeof c === "string"))
    if (!readable) throw new Error("idstack guard: a shell call without a readable command was held (fail closed).")
    const cwd = typeof input.workdir === "string" && input.workdir !== ""
      ? resolve(ctx.location.directory, input.workdir)
      : ctx.location.directory
    let out
    try {
      out = await hook(command, cwd)
    } catch (err) {
      // Fail closed, as the Claude Code and Codex hooks do.
      throw new Error(`idstack guard could not run (${err.message}); the command was held. ` +
        "The operator can check python3 (3.11+) and the idstack checkout, or remove the idstack-guard " +
        "entry from opencode.json.")
    }
    if (!out) return
    const decision = JSON.parse(out)
    if (decision.decision === "deny") throw new Error(decision.reason)
  })
}

const plugin = { id: "idstack-guard", setup }
export default plugin
export const server = plugin
