#!/usr/bin/env bash
# Install idstack and its pstack dependency for Claude Code, Codex, and OpenCode.
set -euo pipefail

# Everything down to this guard has to parse and run on bash 3.2, which macOS still ships.
if [ -z "${BASH_VERSINFO:-}" ] || [ "${BASH_VERSINFO[0]}" -lt 4 ] \
  || { [ "${BASH_VERSINFO[0]}" -eq 4 ] && [ "${BASH_VERSINFO[1]}" -lt 4 ]; }; then
  msg="install.sh needs bash 4.4 or later, this is ${BASH_VERSION:-not bash}; install a newer bash and run it with that"
  printf 'error: %s\n' "$msg" >&2
  case " $* " in
    *" --json "*) printf '{"ok": false, "errors": ["%s"], "exit_code": 3}\n' "$msg" ;;
  esac
  exit 3
fi

PSTACK_MIRROR_URL="https://github.com/backnotprop/pstack.git"
PSTACK_MIRROR_REF="6c75f4e67546c2ddbf9634734c1e3ebbea34861a"
CURSOR_MARKETPLACE="cursor/plugins"

AGENTS_SKILLS_DIR="${AGENTS_SKILLS_DIR:-$HOME/.agents/skills}"
OPENCODE_SKILLS_DIR="${OPENCODE_SKILLS_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills}"
IDSTACK_CACHE_DIR="${IDSTACK_CACHE_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/idstack}"
PSTACK_MANIFEST="$AGENTS_SKILLS_DIR/.pstack-install.json"
IDSTACK_MANIFEST="$OPENCODE_SKILLS_DIR/.idstack-install.json"
IDSTACK_BIN_DIR="${IDSTACK_BIN_DIR:-$HOME/.local/bin}"
CODEX_AGENTS_DIR="${CODEX_HOME:-$HOME/.codex}/agents"
OPENCODE_AGENTS_DIR="${OPENCODE_AGENTS_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode/agents}"
IDSTACK_SRC=""

SUPPORTED=(claude codex opencode)
HARNESSES=()
MODE=install
MODE_FLAG=""
SOURCE="iuliandita/idstack"
SOURCE_LOCAL=0
SOURCE_SET=0
REF=main
FORCE=0
MODELS=1
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FAILED=0
MISSING=0
CLEANUP=()
JSON=0
ERRORS=()
WARNINGS=()
COMPONENTS=()
COMMANDS=()

cleanup() {
  local path
  for path in "${CLEANUP[@]}"; do
    rm -rf "$path"
  done
}

json_str() {
  local s=$1
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}
  s=${s//$'\t'/\\t}
  s=${s//$'\r'/\\r}
  s=${s//[[:cntrl:]]/ }
  printf '"%s"' "$s"
}

json_list() {
  local out="" item
  for item in "$@"; do out+="${out:+, }$(json_str "$item")"; done
  printf '[%s]' "$out"
}

emit_json() {
  local rc=$1 ok=false is_dry=false comps
  case $rc in 0) ok=true ;; esac
  case $MODE in dry-run) is_dry=true ;; esac
  comps=$(IFS=,; printf '%s' "${COMPONENTS[*]}")
  printf '{"ok": %s, "errors": %s, "warnings": %s, "mode": %s, "dry_run": %s, "exit_code": %s, "source": %s, "harnesses": %s, "components": [%s], "commands": %s}\n' \
    "$ok" "$(json_list "${ERRORS[@]}")" "$(json_list "${WARNINGS[@]}")" "$(json_str "$MODE")" "$is_dry" "$rc" \
    "$(json_str "$SOURCE")" "$(json_list "${HARNESSES[@]}")" "$comps" "$(json_list "${COMMANDS[@]}")"
}

finish() {
  local rc=$?
  cleanup
  if [[ $rc -ne 0 && ${#ERRORS[@]} -eq 0 ]]; then
    err "install.sh stopped on a failed command (exit $rc); the output above has the cause"
  fi
  if [[ $rc -gt 3 ]]; then rc=1; fi
  if [[ $JSON -eq 1 ]]; then emit_json "$rc" >&3; fi
  exit "$rc"
}
trap finish EXIT

usage() {
  cat <<'EOF'
Usage: install.sh [OPTIONS]
Install idstack and its pstack dependency for Claude Code, Codex, and OpenCode.

Options:
  --harness LIST  claude, codex, opencode (comma-separated, repeatable).
                  Default: every harness whose CLI is on PATH.
  --check         Report what is installed and what is missing. Changes nothing.
  --dry-run       Print the commands an install would run. Changes nothing.
  --source SRC    Where to install idstack from: owner/repo, a git URL, or a
                  local checkout written as a path (/abs, ./rel, ../rel, or .).
                  Default: iuliandita/idstack.
  --ref REF       Branch or tag for a remote source: main (stable, the default),
                  develop (nightly), or a release tag such as v1.0.0. An existing
                  clone is moved to it; a marketplace that already exists keeps
                  the ref it was added with. Ignored for a local checkout.
  --force         Back up and replace existing skill folders that collide with
                  pstack skills, and pstack model files idstack did not write.
  --no-models     Leave pstack's per-role model files alone.
  --json          Print one JSON object on stdout; human output goes to stderr.
  --uninstall     Remove idstack. pstack is left in place. With --harness, the
                  CLI link and a model file another harness still uses stay.
  -h, --help      Show this help.

pstack comes from the cursor/plugins marketplace on Claude Code, and from the
backnotprop/pstack mirror, pinned to one commit, on Codex and OpenCode. Its
per-role model files are written from config/pstack-models.json.

Environment:
  CLAUDE_CONFIG_DIR, CODEX_HOME   honored by the harness CLIs
  AGENTS_SKILLS_DIR               shared skills dir (default ~/.agents/skills)
  OPENCODE_SKILLS_DIR             OpenCode skills dir (default ~/.config/opencode/skills)
  IDSTACK_CACHE_DIR               clone of idstack for the CLI and OpenCode (default ~/.local/share/idstack)
  IDSTACK_BIN_DIR                 where the idstack CLI is linked (default ~/.local/bin)
  OPENCODE_AGENTS_DIR             OpenCode agents dir (default ~/.config/opencode/agents)
  IDSTACK_CONFIG_DIR              holds models.json, your model overrides (default ~/.config/idstack)

Exit codes:
  0  done, or (with --check) everything is installed
  1  a step failed, or (with --check) something is missing
  2  usage error
  3  a required tool is missing or too old
EOF
}

log() { printf '%s\n' "$*"; }
warn() { WARNINGS+=("$*"); printf 'warning: %s\n' "$*" >&2; }
err() { ERRORS+=("$*"); printf 'error: %s\n' "$*" >&2; }

run() {
  if [[ $MODE == dry-run ]]; then
    COMMANDS+=("$(printf '%q ' "$@")")
    printf 'would run:'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  if ! "$@"; then
    err "command failed: $*"
    FAILED=1
    return 1
  fi
}

would() {
  # would <step>: a --dry-run step the script takes itself, listed with the commands
  COMMANDS+=("$*")
  log "would $*"
}

need() {
  local tool
  for tool in "$@"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      err "missing required tool: $tool; install it and rerun"
      exit 3
    fi
  done
}

jq_op() {
  # jq_op <op> [arg]; reads JSON on stdin. Ops:
  #   claude-plugin ID | codex-plugin ID  -> enabled, disabled, or absent
  #   codex-source ID -> marketplace path an installed Codex plugin came from
  #   claude-market NAME | codex-market NAME -> yes or no
  #   market-values NAME -> every string in that marketplace's entry, one per line
  #   field KEY -> the string value, or empty
  #   lines KEY -> one list item per line
  python3 -I -c '
import json, sys
op, arg = sys.argv[1], sys.argv[2]
try:
    d = json.load(sys.stdin)
except ValueError:
    d = None
def state(items, key):
    for p in items:
        if p.get(key) == arg:
            return "enabled" if p.get("enabled") else "disabled"
    return "absent"
if op == "claude-plugin":
    print(state(d or [], "id"))
elif op == "codex-plugin":
    print(state((d or {}).get("installed", []), "pluginId"))
elif op == "codex-source":
    print(next((p.get("source", {}).get("path", "") for p in (d or {}).get("installed", [])
                if p.get("pluginId") == arg), ""))
elif op in ("claude-market", "codex-market"):
    items = d if isinstance(d, list) else (d or {}).get("marketplaces", [])
    print("yes" if any(m.get("name") == arg for m in items) else "no")
elif op == "market-values":
    def walk(v):
        if isinstance(v, str):
            print(v)
        elif isinstance(v, (dict, list)):
            for x in (v.values() if isinstance(v, dict) else v):
                walk(x)
    for m in (d if isinstance(d, list) else (d or {}).get("marketplaces", [])):
        if m.get("name") == arg:
            walk(m)
elif op == "field":
    print((d or {}).get(arg, ""))
elif op == "lines":
    print("\n".join((d or {}).get(arg, [])))
else:
    sys.exit("unknown op: " + op)
' "$1" "${2:-}"
}

is_local_source() { [[ $SOURCE_LOCAL -eq 1 ]]; }

resolve_source() {
  # A source is local only when it is written as a path: a folder that happens to be named
  # like owner/repo is not one, and a mistyped path is not a GitHub repo.
  case $SOURCE in
    -*) err "--source cannot start with a dash: $SOURCE"; exit 2 ;;
    /*|./*|../*|.|..)
      [[ -d $SOURCE ]] || { err "--source $SOURCE is not a directory"; exit 2; }
      SOURCE=$(cd "$SOURCE" && pwd)
      SOURCE_LOCAL=1 ;;
    *://*|*@*:*) ;;
    *)
      if [[ ! $SOURCE =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9_.-]+$ ]]; then
        err "--source $SOURCE is not owner/repo, a git URL, or a path; write a local checkout as ./$SOURCE or an absolute path"
        exit 2
      fi ;;
  esac
}

valid_name() { [[ $1 =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; }

set_mode() {
  if [[ -n $MODE_FLAG && $MODE_FLAG != "$1" ]]; then
    err "$MODE_FLAG and $1 cannot be combined; pass one of --check, --dry-run, --uninstall"
    exit 2
  fi
  MODE_FLAG=$1
  MODE=${1#--}
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case $1 in
      --harness)
        [[ $# -ge 2 ]] || { err "--harness needs a value"; exit 2; }
        local item
        IFS=',' read -r -a items <<<"$2"
        for item in "${items[@]}"; do
          case $item in
            claude|codex|opencode) HARNESSES+=("$item") ;;
            *) err "unknown harness: $item (expected one of: ${SUPPORTED[*]})"; exit 2 ;;
          esac
        done
        shift 2 ;;
      --check|--dry-run|--uninstall) set_mode "$1"; shift ;;
      --source)
        [[ $# -ge 2 ]] || { err "--source needs a value"; exit 2; }
        SOURCE=$2; SOURCE_SET=1; shift 2 ;;
      --ref)
        [[ $# -ge 2 ]] || { err "--ref needs a value"; exit 2; }
        REF=$2; shift 2 ;;
      --force) FORCE=1; shift ;;
      --no-models) MODELS=0; shift ;;
      --json) shift ;;
      -h|--help) usage; exit 0 ;;
      *) err "unknown option: $1"; usage >&2; exit 2 ;;
    esac
  done
  resolve_source
}

detect_harnesses() {
  if [[ ${#HARNESSES[@]} -gt 0 ]]; then
    return
  fi
  local h
  for h in "${SUPPORTED[@]}"; do
    if command -v "$h" >/dev/null 2>&1; then
      HARNESSES+=("$h")
    fi
  done
  if [[ ${#HARNESSES[@]} -eq 0 ]]; then
    err "no supported harness found on PATH (looked for: ${SUPPORTED[*]}); pass --harness"
    exit 3
  fi
}

wants() {
  local h
  for h in "${HARNESSES[@]}"; do
    [[ $h == "$1" ]] && return 0
  done
  return 1
}

status() {
  # status <component> <state> [detail]
  printf '  %-28s %s%s\n' "$1" "$2" "${3:+ ($3)}"
  COMPONENTS+=("{\"name\": $(json_str "$1"), \"state\": $(json_str "$2"), \"detail\": $(json_str "${3:-}")}")
  if [[ $2 != ok ]]; then
    MISSING=1
    ERRORS+=("missing: $1 ($2)")
  fi
}

# ---------- Claude Code ----------

claude_plugin_state() {
  # prints: enabled, disabled, absent, or unknown when the CLI cannot list its plugins
  local out
  out=$(claude plugin list --json 2>/dev/null) || { printf 'unknown\n'; return 0; }
  jq_op claude-plugin "$1" <<<"$out"
}

claude_has_marketplace() {
  [[ $(claude plugin marketplace list --json 2>/dev/null | jq_op claude-market "$1") == yes ]]
}

plugin_status() {
  # plugin_status <plugin id> <state> <cli>
  case $2 in
    enabled) status "$1" ok ;;
    unknown) status "$1" unknown "$3 plugin list --json failed" ;;
    *) status "$1" "$2" ;;
  esac
}

market_source_differs() {
  # market_source_differs <claude|codex>: true when the idstack marketplace there names another source
  local values
  values=$("$1" plugin marketplace list --json 2>/dev/null | jq_op market-values idstack) || return 1
  [[ -n $values ]] && ! grep -qF -- "$SOURCE" <<<"$values"
}

warn_market_source() {
  # warn_market_source <claude|codex> <label>: --source does not move a marketplace that already exists
  if [[ $SOURCE_SET -eq 1 ]] && market_source_differs "$1"; then
    warn "the idstack marketplace in $2 was added from another source, so --source $SOURCE was not applied to it; remove it with '$1 plugin marketplace remove idstack' and rerun"
  fi
}

claude_check() {
  log "Claude Code"
  plugin_status "pstack@cursor-plugins" "$(claude_plugin_state pstack@cursor-plugins)" claude
  plugin_status "idstack@idstack" "$(claude_plugin_state idstack@idstack)" claude
}

claude_install() {
  log "Claude Code"
  if ! claude_has_marketplace cursor-plugins; then
    run claude plugin marketplace add "$CURSOR_MARKETPLACE"
  fi
  if [[ $(claude_plugin_state pstack@cursor-plugins) == absent ]]; then
    run claude plugin install pstack@cursor-plugins
  else
    log "  pstack@cursor-plugins already installed"
  fi
  if ! claude_has_marketplace idstack; then
    if is_local_source; then run claude plugin marketplace add "$SOURCE"; else run claude plugin marketplace add "$SOURCE#$REF"; fi
  else
    warn_market_source claude "Claude Code"
    run claude plugin marketplace update idstack
  fi
  if [[ $(claude_plugin_state idstack@idstack) == absent ]]; then
    run claude plugin install idstack@idstack
  else
    run claude plugin update idstack@idstack
  fi
  if [[ $MODE == install ]]; then
    [[ $(claude_plugin_state pstack@cursor-plugins) == enabled ]] || { err "pstack is not enabled in Claude Code after install"; FAILED=1; }
    [[ $(claude_plugin_state idstack@idstack) == enabled ]] || { err "idstack is not enabled in Claude Code after install"; FAILED=1; }
  fi
}

claude_uninstall() {
  log "Claude Code"
  if ! command -v claude >/dev/null 2>&1; then
    warn "claude is not on PATH, so its idstack plugin was not touched; remove it with 'claude plugin uninstall idstack@idstack'"
  elif [[ $(claude_plugin_state idstack@idstack) != absent ]]; then
    run claude plugin uninstall idstack@idstack || true
  else
    log "  idstack not installed"
  fi
}

# ---------- Codex ----------

codex_plugin_state() {
  local out
  out=$(codex plugin list --json 2>/dev/null) || { printf 'unknown\n'; return 0; }
  jq_op codex-plugin "$1" <<<"$out"
}

codex_has_marketplace() {
  [[ $(codex plugin marketplace list --json 2>/dev/null | jq_op codex-market "$1") == yes ]]
}

codex_plugin_outdated() {
  # true when the marketplace version is not among the versions in the Codex plugin cache
  local src want
  src=$(codex plugin list --json 2>/dev/null | jq_op codex-source idstack@idstack)
  # Codex names its cache after the version in .claude-plugin/plugin.json, not the root plugin.json.
  [[ -n $src && -f $src/.claude-plugin/plugin.json ]] || return 1
  want=$(jq_op field version <"$src/.claude-plugin/plugin.json")
  [[ -n $want && ! -d ${CODEX_HOME:-$HOME/.codex}/plugins/cache/idstack/idstack/$want ]]
}

codex_check() {
  log "Codex"
  local state
  state=$(codex_plugin_state idstack@idstack)
  if [[ $state == enabled ]] && codex_plugin_outdated; then
    status "idstack@idstack" outdated "a newer version is in the marketplace"
  else
    plugin_status "idstack@idstack" "$state" codex
  fi
  check_set "agents in $CODEX_AGENTS_DIR" "$CODEX_AGENTS_DIR" "*.toml"
}

codex_install() {
  log "Codex"
  if ! codex_has_marketplace idstack; then
    if is_local_source; then run codex plugin marketplace add "$SOURCE"; else run codex plugin marketplace add "$SOURCE" --ref "$REF"; fi
  else
    warn_market_source codex Codex
    is_local_source || run codex plugin marketplace upgrade idstack
  fi
  if [[ $(codex_plugin_state idstack@idstack) == absent ]]; then
    run codex plugin add idstack@idstack
  elif codex_plugin_outdated; then
    # Codex has no plugin update and caches one copy per version, so reinstall.
    run codex plugin remove idstack@idstack
    run codex plugin add idstack@idstack
  else
    log "  idstack@idstack already installed"
  fi
  if [[ $MODE == install && $(codex_plugin_state idstack@idstack) != enabled ]]; then
    err "idstack is not enabled in Codex after install"
    FAILED=1
  fi
  # Codex plugins cannot ship agents, so they are linked into the user agents dir.
  idstack_checkout
  link_set agents "$IDSTACK_SRC/harness/codex/agents" "*.toml" "$CODEX_AGENTS_DIR"
}

codex_uninstall() {
  log "Codex"
  if ! command -v codex >/dev/null 2>&1; then
    warn "codex is not on PATH, so its idstack plugin was not touched; remove it with 'codex plugin remove idstack@idstack'"
  elif [[ $(codex_plugin_state idstack@idstack) != absent ]]; then
    run codex plugin remove idstack@idstack || true
  else
    log "  idstack not installed"
  fi
  unlink_set "$CODEX_AGENTS_DIR"
}

# ---------- pstack mirror (Codex and OpenCode) ----------

pstack_installed_ref() {
  if [[ -f $PSTACK_MANIFEST ]]; then
    jq_op field commit <"$PSTACK_MANIFEST"
  fi
}

pstack_missing() {
  # prints how many skills the pstack manifest lists that are no longer on disk
  local name missing=0
  while IFS= read -r name; do
    [[ -n $name && ! -f $AGENTS_SKILLS_DIR/$name/SKILL.md ]] && missing=$((missing + 1))
  done < <(jq_op lines skills <"$PSTACK_MANIFEST")
  printf '%s\n' "$missing"
}

pstack_check() {
  local ref missing
  ref=$(pstack_installed_ref)
  if [[ -z $ref ]]; then
    if [[ -f $PSTACK_MANIFEST ]]; then
      status "pstack in $AGENTS_SKILLS_DIR" incomplete "the last copy did not finish"
    elif [[ -f $AGENTS_SKILLS_DIR/poteto-mode/SKILL.md ]]; then
      status "pstack in $AGENTS_SKILLS_DIR" ok "installed outside this script"
    else
      status "pstack in $AGENTS_SKILLS_DIR" absent
    fi
  elif [[ $ref != "$PSTACK_MIRROR_REF" ]]; then
    status "pstack in $AGENTS_SKILLS_DIR" outdated "installed ${ref:0:7}, pinned ${PSTACK_MIRROR_REF:0:7}"
  else
    missing=$(pstack_missing)
    if ((missing)); then
      status "pstack in $AGENTS_SKILLS_DIR" "broken ($missing missing)"
    else
      status "pstack in $AGENTS_SKILLS_DIR" ok "${ref:0:7}"
    fi
  fi
}

pstack_manifest() {
  # pstack_manifest <commit>: skill names on stdin. An empty commit marks a copy in progress.
  # Written beside the manifest and renamed over it, so a reader never sees half a file.
  python3 -I -c 'import json, os, sys
source, commit, dest = sys.argv[1:4]
names = list(dict.fromkeys(l for l in sys.stdin.read().splitlines() if l))
data = {"source": source, **({"commit": commit} if commit else {}), "skills": names}
with open(dest + ".tmp", "w") as f:
    json.dump(data, f, indent=2)
os.replace(dest + ".tmp", dest)' "$PSTACK_MIRROR_URL" "$1" "$PSTACK_MANIFEST"
}

pstack_install() {
  log "pstack for Codex and OpenCode ($AGENTS_SKILLS_DIR)"
  local ref previous=() name
  ref=$(pstack_installed_ref)
  if [[ $ref == "$PSTACK_MIRROR_REF" && $(pstack_missing) -eq 0 ]]; then
    log "  pstack ${ref:0:7} already installed"
    return
  fi
  if [[ -f $PSTACK_MANIFEST ]]; then
    mapfile -t previous < <(jq_op lines skills <"$PSTACK_MANIFEST")
    # These names end up in rm -rf, so each has to be one plain folder name.
    for name in "${previous[@]}"; do
      if [[ -n $name ]] && ! valid_name "$name"; then
        err "$PSTACK_MANIFEST lists '$name', which is not a plain skill folder name; fix or delete that file and rerun"
        FAILED=1
        return
      fi
    done
    # Only a finished copy records its commit.
    [[ -n $ref ]] || log "  the last pstack copy did not finish; redoing it"
  elif [[ -f $AGENTS_SKILLS_DIR/poteto-mode/SKILL.md ]]; then
    log "  pstack already present (installed outside this script); leaving it alone"
    return
  fi
  if [[ $MODE == dry-run ]]; then
    would "fetch $PSTACK_MIRROR_URL at ${PSTACK_MIRROR_REF:0:7} and copy its skills into $AGENTS_SKILLS_DIR"
    return
  fi

  local tmp
  tmp=$(mktemp -d)
  CLEANUP+=("$tmp")
  if ! { git -C "$tmp" init -q \
    && git -C "$tmp" fetch -q --depth 1 "$PSTACK_MIRROR_URL" "$PSTACK_MIRROR_REF" \
    && git -C "$tmp" checkout -q FETCH_HEAD; }; then
    err "could not fetch $PSTACK_MIRROR_URL at ${PSTACK_MIRROR_REF:0:7}; check the network and rerun"
    FAILED=1
    return
  fi

  local names=()
  for name in "$tmp"/skills/*/; do
    name=$(basename "$name")
    [[ -f $tmp/skills/$name/SKILL.md ]] && valid_name "$name" && names+=("$name")
  done
  if [[ ${#names[@]} -eq 0 ]]; then
    err "the pstack mirror at ${PSTACK_MIRROR_REF:0:7} has no skills"
    FAILED=1
    return
  fi

  local collisions=()
  for name in "${names[@]}"; do
    if [[ -e $AGENTS_SKILLS_DIR/$name ]] && ! printf '%s\n' "${previous[@]}" | grep -qxF -- "$name"; then
      collisions+=("$name")
    fi
  done
  if [[ ${#collisions[@]} -gt 0 && $FORCE -eq 0 ]]; then
    err "these skills in $AGENTS_SKILLS_DIR were not installed by this script and share a name with pstack skills: ${collisions[*]}"
    err "rerun with --force to back them up and replace them"
    FAILED=1
    return
  fi

  # Copy everything into a folder beside the target first, so the slow part cannot leave the
  # skills dir half-written; each skill is then renamed into place.
  local stage
  mkdir -p "$AGENTS_SKILLS_DIR"
  rm -rf "${AGENTS_SKILLS_DIR:?}"/.pstack-stage.*
  if ! stage=$(mktemp -d "$AGENTS_SKILLS_DIR/.pstack-stage.XXXXXX"); then
    err "could not create a staging folder in $AGENTS_SKILLS_DIR"
    FAILED=1
    return
  fi
  CLEANUP+=("$stage")
  for name in "${names[@]}"; do
    if ! cp -R "$tmp/skills/$name" "$stage/$name"; then
      err "could not copy the pstack skill $name into $AGENTS_SKILLS_DIR"
      FAILED=1
      return
    fi
  done

  if [[ ${#collisions[@]} -gt 0 ]]; then
    local backup
    backup="$(dirname "$AGENTS_SKILLS_DIR")/.idstack-backups/$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p "$backup"
    for name in "${collisions[@]}"; do
      mv "$AGENTS_SKILLS_DIR/$name" "$backup/$name"
    done
    log "  backed up ${#collisions[@]} colliding skills to $backup"
  fi

  # No commit in the manifest yet: a run killed from here on is redone, never taken for an install.
  printf '%s\n' "${previous[@]}" "${names[@]}" | pstack_manifest ""
  for name in "${names[@]}"; do
    rm -rf "${AGENTS_SKILLS_DIR:?}/$name"
    mv "$stage/$name" "$AGENTS_SKILLS_DIR/$name"
  done
  for name in "${previous[@]}"; do
    if [[ -n $name ]] && ! printf '%s\n' "${names[@]}" | grep -qxF -- "$name"; then
      rm -rf "${AGENTS_SKILLS_DIR:?}/$name"
    fi
  done
  printf '%s\n' "${names[@]}" | pstack_manifest "$PSTACK_MIRROR_REF"
  log "  installed ${#names[@]} pstack skills at ${PSTACK_MIRROR_REF:0:7}"
}

# ---------- OpenCode ----------

idstack_checkout() {
  # sets IDSTACK_SRC to a local path holding the idstack source, fetching it once per run
  [[ -n $IDSTACK_SRC ]] && return
  if is_local_source; then
    IDSTACK_SRC=$SOURCE
    return
  fi
  local url=$SOURCE
  [[ $url != *://* && $url != *@*:* ]] && url="https://github.com/$url.git"
  IDSTACK_SRC="$IDSTACK_CACHE_DIR/src"
  [[ $MODE == dry-run ]] && return
  if [[ ! -d $IDSTACK_SRC/.git ]]; then
    mkdir -p "$IDSTACK_CACHE_DIR"
    git clone -q -- "$url" "$IDSTACK_SRC" || { err "could not clone $url into $IDSTACK_SRC"; exit 1; }
  elif [[ $(git -C "$IDSTACK_SRC" remote get-url origin 2>/dev/null) != "$url" ]]; then
    log "  pointing the clone in $IDSTACK_SRC at $url"
    git -C "$IDSTACK_SRC" remote set-url origin "$url" || { err "could not point $IDSTACK_SRC at $url"; exit 1; }
  fi
  checkout_ref "$IDSTACK_SRC" || {
    err "could not check out $REF in $IDSTACK_SRC (from $url); check --ref, or move that folder away and rerun"
    exit 1
  }
}

checkout_ref() {
  # checkout_ref <clone>: a branch is fast-forwarded to origin, a tag is checked out detached
  local repo=$1
  git -C "$repo" fetch -q --tags origin || return 1
  if git -C "$repo" show-ref --verify -q "refs/remotes/origin/$REF"; then
    if git -C "$repo" show-ref --verify -q "refs/heads/$REF"; then
      git -C "$repo" checkout -q "$REF" || return 1
    else
      git -C "$repo" checkout -q -b "$REF" --track "origin/$REF" || return 1
    fi
    git -C "$repo" merge -q --ff-only "origin/$REF"
  elif git -C "$repo" show-ref --verify -q "refs/tags/$REF"; then
    git -C "$repo" checkout -q --detach "refs/tags/$REF"
  else
    return 1
  fi
}

owned_link() {
  # owned_link <link> <expected target> [manifest]: true when <link> is a symlink idstack made
  local link=$1 want=$2 manifest=${3:-}
  [[ -L $link ]] || return 1
  [[ $(readlink "$link") == "$want" ]] && return 0
  [[ -n $manifest && -f $manifest ]] || return 1
  local source
  source=$(jq_op field source <"$manifest")
  [[ -n $source && $(readlink "$link") == "$source/"* ]] || return 1
  { jq_op lines files <"$manifest"; jq_op lines skills <"$manifest"; } | grep -xF "$(basename "$link")" >/dev/null
}

prune_links() {
  # prune_links <dest dir> <manifest> <key> [current names]: remove recorded links the source no longer has
  local dest=$1 manifest=$2 key=$3 name
  shift 3
  [[ -f $manifest ]] || return 0
  while IFS= read -r name; do
    [[ -n $name ]] || continue
    printf '%s\n' "$@" | grep -qxF -- "$name" && continue
    owned_link "$dest/$name" "" "$manifest" && rm "$dest/$name"
  done < <(jq_op lines "$key" <"$manifest")
  return 0
}

link_set() {
  # link_set <label> <src dir> <glob> <dest dir>: link matching files, recorded in <dest>/.idstack-install.json
  local label=$1 from=$2 glob=$3 dest=$4 path name linked=()
  if [[ $MODE == dry-run ]]; then
    would "link $from/$glob into $dest"
    return
  fi
  mkdir -p "$dest"
  for path in "$from"/$glob; do
    [[ -f $path ]] || continue
    name=$(basename "$path")
    if [[ -e $dest/$name || -L $dest/$name ]] && ! owned_link "$dest/$name" "$path" "$dest/.idstack-install.json"; then
      err "$dest/$name exists and is not an idstack link; leaving it alone"
      FAILED=1
      continue
    fi
    ln -sfn "$path" "$dest/$name"
    linked+=("$name")
  done
  prune_links "$dest" "$dest/.idstack-install.json" files "${linked[@]}"
  printf '%s\n' "${linked[@]}" | python3 -I -c 'import json, sys
names = [l for l in sys.stdin.read().splitlines() if l]
json.dump({"source": sys.argv[1], "files": names}, open(sys.argv[2], "w"), indent=2)' "$from" "$dest/.idstack-install.json"
  log "  linked ${#linked[@]} $label into $dest"
}

unlink_set() {
  # unlink_set <dest dir>: remove the links link_set recorded
  local dest=$1 name manifest=$1/.idstack-install.json
  [[ -f $manifest ]] || return 0
  while IFS= read -r name; do
    [[ -n $name ]] && owned_link "$dest/$name" "" "$manifest" && run rm "$dest/$name"
  done < <(jq_op lines files <"$manifest")
  run rm "$dest/.idstack-install.json"
}

check_set() {
  # check_set <label> <dest dir> [glob]: ok when every recorded link resolves and nothing in the
  # source is left unlinked. A skills manifest records the checkout, a files manifest the folder.
  local manifest=$2/.idstack-install.json names name source path broken=0 unlinked=0
  if [[ ! -f $manifest ]]; then status "$1" absent; return; fi
  names=$(jq_op lines files <"$manifest"; jq_op lines skills <"$manifest")
  while IFS= read -r name; do
    [[ -n $name && ! ( -L $2/$name && -e $2/$name ) ]] && broken=$((broken + 1))
  done <<<"$names"
  source=$(jq_op field source <"$manifest")
  for path in "$source"/${3:-skills/*/}; do
    [[ -e $path ]] || continue
    grep -qxF -- "$(basename "$path")" <<<"$names" || unlinked=$((unlinked + 1))
  done
  if ((broken)); then
    status "$1" "broken ($broken missing)"
  elif ((unlinked)); then
    status "$1" outdated "$unlinked in $source not linked"
  else
    status "$1" ok
  fi
}

cli_check() {
  log "idstack CLI"
  local link=$IDSTACK_BIN_DIR/idstack
  if [[ ! -e $link && ! -L $link ]]; then
    status "$link" absent
  elif [[ ! -L $link || $(readlink "$link") != */bin/idstack ]]; then
    status "$link" foreign "not an idstack link"
  elif [[ ! -x $link ]]; then
    status "$link" broken "its target is gone"
  else
    status "$link" ok
  fi
}

cli_install() {
  log "idstack CLI ($IDSTACK_BIN_DIR)"
  idstack_checkout
  local link=$IDSTACK_BIN_DIR/idstack
  if [[ -e $link || -L $link ]] && ! { [[ -L $link ]] && [[ $(readlink "$link") == */bin/idstack ]]; }; then
    err "$link exists and is not an idstack link; leaving it alone"
    FAILED=1
    return
  fi
  run mkdir -p "$IDSTACK_BIN_DIR"
  run ln -sfn "$IDSTACK_SRC/bin/idstack" "$link"
  case ":$PATH:" in *":$IDSTACK_BIN_DIR:"*) ;; *) warn "$IDSTACK_BIN_DIR is not on PATH" ;; esac
}

guard_registered() {
  # guard_registered <codex|opencode>: true when a config file names the idstack guard; sets GUARD_FILE
  local dir files mark
  if [[ $1 == codex ]]; then
    files=("${CODEX_HOME:-$HOME/.codex}/hooks.json")
    mark="idstack guard hook"
  else
    dir=${XDG_CONFIG_HOME:-$HOME/.config}/opencode
    files=("$dir/opencode.json" "$dir/opencode.jsonc")
    mark="harness/opencode/guard"
  fi
  for GUARD_FILE in "${files[@]}"; do
    [[ -f $GUARD_FILE ]] && grep -qF -- "$mark" "$GUARD_FILE" && return 0
  done
  return 1
}

still_used_by() {
  # still_used_by <harness...>: sets USERS to those harnesses this run leaves alone that still have idstack
  local h
  USERS=()
  for h in "$@"; do
    wants "$h" && continue
    case $h in
      claude) command -v claude >/dev/null 2>&1 && [[ $(claude_plugin_state idstack@idstack) != absent ]] && USERS+=("$h") ;;
      codex) [[ -f $CODEX_AGENTS_DIR/.idstack-install.json ]] && USERS+=("$h") ;;
      opencode) [[ -f $IDSTACK_MANIFEST || -f $OPENCODE_AGENTS_DIR/.idstack-install.json ]] && USERS+=("$h") ;;
    esac
  done
  [[ ${#USERS[@]} -gt 0 ]]
}

cli_uninstall() {
  log "idstack CLI"
  local link=$IDSTACK_BIN_DIR/idstack exe h kept=0
  [[ -L $link && $(readlink "$link") == */bin/idstack ]] || { log "  no idstack link at $link"; return 0; }
  # A dangling link cannot run, so this checkout removes the hooks for it.
  exe=$link
  [[ -x $link ]] || exe=$SCRIPT_DIR/bin/idstack
  # Remove the guard hooks first: they call the checkout behind the link.
  for h in codex opencode; do
    if ! wants "$h" || ! guard_registered "$h"; then continue; fi
    "$exe" guard uninstall --harness "$h" || true
    if guard_registered "$h"; then
      err "could not remove the $h guard from $GUARD_FILE; remove its entry by hand and rerun --uninstall"
      FAILED=1
      kept=1
    fi
  done
  if [[ $kept -eq 1 && -x $link ]]; then
    log "  kept $link: a guard hook still calls it"
    return 0
  fi
  if still_used_by "${SUPPORTED[@]}"; then
    log "  kept $link: ${USERS[*]} still uses it"
    return 0
  fi
  run rm "$link"
}

opencode_check() {
  log "OpenCode"
  check_set "idstack in $OPENCODE_SKILLS_DIR" "$OPENCODE_SKILLS_DIR"
  check_set "agents in $OPENCODE_AGENTS_DIR" "$OPENCODE_AGENTS_DIR" "*.md"
}

opencode_install() {
  log "OpenCode ($OPENCODE_SKILLS_DIR)"
  local src name linked=()
  idstack_checkout
  src=$IDSTACK_SRC
  link_set agents "$src/harness/opencode/agents" "*.md" "$OPENCODE_AGENTS_DIR"
  if [[ $MODE == dry-run ]]; then
    would "link each skill folder under $src/skills into $OPENCODE_SKILLS_DIR"
    return
  fi
  mkdir -p "$OPENCODE_SKILLS_DIR"
  if [[ -d $src/skills ]]; then
    for name in "$src"/skills/*/; do
      [[ -d $name ]] || continue
      name=$(basename "$name")
      if [[ -e $OPENCODE_SKILLS_DIR/$name || -L $OPENCODE_SKILLS_DIR/$name ]] \
        && ! owned_link "$OPENCODE_SKILLS_DIR/$name" "$src/skills/$name" "$IDSTACK_MANIFEST"; then
        err "$OPENCODE_SKILLS_DIR/$name exists and is not an idstack link; leaving it alone"
        FAILED=1
        continue
      fi
      ln -sfn "$src/skills/$name" "$OPENCODE_SKILLS_DIR/$name"
      linked+=("$name")
    done
  fi
  prune_links "$OPENCODE_SKILLS_DIR" "$IDSTACK_MANIFEST" skills "${linked[@]}"
  printf '%s\n' "${linked[@]}" | python3 -I -c 'import json, sys
names = [l for l in sys.stdin.read().splitlines() if l]
json.dump({"source": sys.argv[1], "skills": names}, open(sys.argv[2], "w"), indent=2)' "$src" "$IDSTACK_MANIFEST"
  if [[ ${#linked[@]} -eq 0 ]]; then
    log "  idstack has no skills yet; nothing to link"
  else
    log "  linked ${#linked[@]} idstack skills"
  fi
}

opencode_uninstall() {
  log "OpenCode"
  unlink_set "$OPENCODE_AGENTS_DIR"
  if [[ ! -f $IDSTACK_MANIFEST ]]; then
    log "  idstack not installed"
    return
  fi
  local name
  while IFS= read -r name; do
    [[ -n $name ]] && owned_link "$OPENCODE_SKILLS_DIR/$name" "" "$IDSTACK_MANIFEST" && run rm "$OPENCODE_SKILLS_DIR/$name"
  done < <(jq_op lines skills <"$IDSTACK_MANIFEST")
  run rm "$IDSTACK_MANIFEST"
}

models_step() {
  # models_step [--check --porcelain|--dry-run|--uninstall]
  [[ $MODELS -eq 1 ]] || return 0
  local args=()
  wants claude && args+=(--target claude)
  if wants codex || wants opencode; then
    # Codex and OpenCode read one file, so it stays while either still has idstack.
    if [[ ${1:-} == --uninstall ]] && still_used_by codex opencode; then
      log "  kept the Codex and OpenCode model file: ${USERS[*]} still uses it"
    else
      args+=(--target agents)
    fi
  fi
  [[ ${#args[@]} -gt 0 ]] || return 0
  [[ $FORCE -eq 1 ]] && args+=(--force)
  python3 -I "$SCRIPT_DIR/scripts/pstack_models.py" "${args[@]}" "$@"
}

models_check() {
  [[ $MODELS -eq 1 ]] || return 0
  local out rc=0 target state detail seen=0
  out=$(models_step --check --porcelain) || rc=$?
  while IFS=$'\t' read -r target state detail; do
    [[ -n $state ]] || continue
    status "pstack models ($target)" "$state" "$detail"
    seen=1
  done <<<"$out"
  if [[ $rc -ne 0 && $seen -eq 0 ]]; then
    MISSING=1
    ERRORS+=("the pstack model config is not valid, so the model files were not checked")
  fi
}

models_dry_run() {
  local out line
  out=$(models_step --dry-run) || FAILED=1
  while IFS= read -r line; do
    case $line in
      "would "*) would "${line#would }" ;;
      ?*) log "$line" ;;
    esac
  done <<<"$out"
}

main() {
  local arg
  for arg in "$@"; do
    if [[ $arg == --json ]]; then
      JSON=1
      exec 3>&1 1>&2
      break
    fi
  done
  parse_args "$@"
  need python3 git
  if ! python3 -I -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    err "python3 is too old: found $(python3 -V 2>&1 | head -n 1), need Python 3.11 or later"
    exit 3
  fi
  detect_harnesses
  local h
  for h in "${HARNESSES[@]}"; do
    if ! command -v "$h" >/dev/null 2>&1; then
      if [[ $MODE == uninstall ]]; then
        : # links and files can still go; the harness step says what it left behind
      elif [[ $h == opencode ]]; then
        warn "opencode is not on PATH; installing its skills anyway"
      else
        err "$h CLI not found on PATH; install it or drop it from --harness"
        exit 3
      fi
    fi
  done

  log "idstack $MODE for: ${HARNESSES[*]} (source: $SOURCE$(is_local_source || printf ' @ %s' "$REF"))"
  case $MODE in
    check)
      wants claude && claude_check
      if wants codex || wants opencode; then
        log "pstack mirror"
        pstack_check
      fi
      wants codex && codex_check
      wants opencode && opencode_check
      cli_check
      log "pstack model files"
      models_check
      if [[ $MISSING -ne 0 ]]; then
        log "Something is missing. Run install.sh to fix it."
        exit 1
      fi
      log "Everything is installed."
      ;;
    install|dry-run)
      wants claude && claude_install
      if wants codex || wants opencode; then pstack_install; fi
      wants codex && codex_install
      wants opencode && opencode_install
      cli_install
      log "pstack model files"
      if [[ $MODE == dry-run ]]; then models_dry_run; else models_step || FAILED=1; fi
      if [[ $FAILED -ne 0 ]]; then
        err "install finished with errors"
        exit 1
      fi
      log "Done. Restart running agent sessions to load the plugins."
      ;;
    uninstall)
      cli_uninstall
      wants claude && claude_uninstall
      wants codex && codex_uninstall
      wants opencode && opencode_uninstall
      log "pstack model files"
      models_step --uninstall || FAILED=1
      if [[ $FAILED -ne 0 ]]; then
        err "uninstall finished with errors"
        exit 1
      fi
      log "Done. pstack was left in place."
      ;;
  esac
}

main "$@"
