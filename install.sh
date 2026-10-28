#!/usr/bin/env bash
# Install idstack and its pstack dependency for Claude Code, Codex, and OpenCode.
set -euo pipefail

PSTACK_MIRROR_URL="https://github.com/backnotprop/pstack.git"
PSTACK_MIRROR_REF="37d989cabf310ea2d7631f1d006117ca4cc8a799"
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
SOURCE="iuliandita/idstack"
FORCE=0
MODELS=1
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FAILED=0
MISSING=0
CLEANUP=()

cleanup() {
  local path
  for path in "${CLEANUP[@]}"; do
    rm -rf "$path"
  done
}
trap cleanup EXIT

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
                  local checkout. Default: iuliandita/idstack.
  --force         Back up and replace existing skill folders that collide with
                  pstack skills, and pstack model files idstack did not write.
  --no-models     Leave pstack's per-role model files alone.
  --uninstall     Remove idstack. pstack is left in place.
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

Exit codes:
  0  done, or (with --check) everything is installed
  1  a step failed, or (with --check) something is missing
  2  usage error
  3  a required tool is missing
EOF
}

log() { printf '%s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
err() { printf 'error: %s\n' "$*" >&2; }

run() {
  if [[ $MODE == dry-run ]]; then
    printf 'would run:'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

need() {
  local tool
  for tool in "$@"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      err "missing required tool: $tool"
      exit 3
    fi
  done
}

jq_op() {
  # jq_op <op> [arg]; reads JSON on stdin. Ops:
  #   claude-plugin ID | codex-plugin ID  -> enabled, disabled, or absent
  #   codex-source ID -> marketplace path an installed Codex plugin came from
  #   claude-market NAME | codex-market NAME -> yes or no
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
elif op == "field":
    print((d or {}).get(arg, ""))
elif op == "lines":
    print("\n".join((d or {}).get(arg, [])))
else:
    sys.exit("unknown op: " + op)
' "$1" "${2:-}"
}

is_local_source() { [[ -d $SOURCE ]]; }

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
      --check) MODE=check; shift ;;
      --dry-run) MODE=dry-run; shift ;;
      --uninstall) MODE=uninstall; shift ;;
      --source)
        [[ $# -ge 2 ]] || { err "--source needs a value"; exit 2; }
        SOURCE=$2; shift 2 ;;
      --force) FORCE=1; shift ;;
      --no-models) MODELS=0; shift ;;
      -h|--help) usage; exit 0 ;;
      *) err "unknown option: $1"; usage >&2; exit 2 ;;
    esac
  done
  if is_local_source; then
    SOURCE=$(cd "$SOURCE" && pwd)
  fi
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
  if [[ $2 != ok ]]; then
    MISSING=1
  fi
}

# ---------- Claude Code ----------

claude_plugin_state() {
  # prints: enabled, disabled, or absent
  claude plugin list --json 2>/dev/null | jq_op claude-plugin "$1"
}

claude_has_marketplace() {
  [[ $(claude plugin marketplace list --json 2>/dev/null | jq_op claude-market "$1") == yes ]]
}

claude_check() {
  log "Claude Code"
  local pstack idstack
  pstack=$(claude_plugin_state pstack@cursor-plugins)
  idstack=$(claude_plugin_state idstack@idstack)
  if [[ $pstack == enabled ]]; then status "pstack@cursor-plugins" ok; else status "pstack@cursor-plugins" "$pstack"; fi
  if [[ $idstack == enabled ]]; then status "idstack@idstack" ok; else status "idstack@idstack" "$idstack"; fi
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
    run claude plugin marketplace add "$SOURCE"
  else
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
  if [[ $(claude_plugin_state idstack@idstack) != absent ]]; then
    run claude plugin uninstall idstack@idstack
  else
    log "  idstack not installed"
  fi
}

# ---------- Codex ----------

codex_plugin_state() {
  codex plugin list --json 2>/dev/null | jq_op codex-plugin "$1"
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
  elif [[ $state == enabled ]]; then
    status "idstack@idstack" ok
  else
    status "idstack@idstack" "$state"
  fi
  check_set "agents in $CODEX_AGENTS_DIR" "$CODEX_AGENTS_DIR"
}

codex_install() {
  log "Codex"
  if ! codex_has_marketplace idstack; then
    run codex plugin marketplace add "$SOURCE"
  elif ! is_local_source; then
    run codex plugin marketplace upgrade idstack
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
  if [[ $(codex_plugin_state idstack@idstack) != absent ]]; then
    run codex plugin remove idstack@idstack
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

pstack_check() {
  local ref
  ref=$(pstack_installed_ref)
  if [[ -z $ref ]]; then
    if [[ -f $AGENTS_SKILLS_DIR/poteto-mode/SKILL.md ]]; then
      status "pstack in $AGENTS_SKILLS_DIR" ok "installed outside this script"
    else
      status "pstack in $AGENTS_SKILLS_DIR" absent
    fi
  elif [[ $ref != "$PSTACK_MIRROR_REF" ]]; then
    status "pstack in $AGENTS_SKILLS_DIR" outdated "installed ${ref:0:7}, pinned ${PSTACK_MIRROR_REF:0:7}"
  else
    status "pstack in $AGENTS_SKILLS_DIR" ok "${ref:0:7}"
  fi
}

pstack_install() {
  log "pstack for Codex and OpenCode ($AGENTS_SKILLS_DIR)"
  local ref
  ref=$(pstack_installed_ref)
  if [[ $ref == "$PSTACK_MIRROR_REF" ]]; then
    log "  pstack ${ref:0:7} already installed"
    return
  fi
  if [[ -z $ref && -f $AGENTS_SKILLS_DIR/poteto-mode/SKILL.md ]]; then
    log "  pstack already present (installed outside this script); leaving it alone"
    return
  fi
  if [[ $MODE == dry-run ]]; then
    log "would fetch $PSTACK_MIRROR_URL at ${PSTACK_MIRROR_REF:0:7} and copy its skills into $AGENTS_SKILLS_DIR"
    return
  fi

  local tmp
  tmp=$(mktemp -d)
  CLEANUP+=("$tmp")
  git -C "$tmp" init -q
  git -C "$tmp" fetch -q --depth 1 "$PSTACK_MIRROR_URL" "$PSTACK_MIRROR_REF"
  git -C "$tmp" checkout -q FETCH_HEAD

  local names=() name
  for name in "$tmp"/skills/*/; do
    name=$(basename "$name")
    [[ -f $tmp/skills/$name/SKILL.md ]] && names+=("$name")
  done
  if [[ ${#names[@]} -eq 0 ]]; then
    err "the pstack mirror at ${PSTACK_MIRROR_REF:0:7} has no skills"
    FAILED=1
    return
  fi

  local previous=()
  if [[ -f $PSTACK_MANIFEST ]]; then
    mapfile -t previous < <(jq_op lines skills <"$PSTACK_MANIFEST")
  fi
  local collisions=()
  for name in "${names[@]}"; do
    if [[ -e $AGENTS_SKILLS_DIR/$name ]] && ! printf '%s\n' "${previous[@]}" | grep -qxF "$name"; then
      collisions+=("$name")
    fi
  done
  if [[ ${#collisions[@]} -gt 0 ]]; then
    if [[ $FORCE -eq 0 ]]; then
      err "these skills in $AGENTS_SKILLS_DIR were not installed by this script and share a name with pstack skills: ${collisions[*]}"
      err "rerun with --force to back them up and replace them"
      FAILED=1
      return
    fi
    local backup
    backup="$(dirname "$AGENTS_SKILLS_DIR")/.idstack-backups/$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p "$backup"
    for name in "${collisions[@]}"; do
      mv "$AGENTS_SKILLS_DIR/$name" "$backup/$name"
    done
    log "  backed up ${#collisions[@]} colliding skills to $backup"
  fi

  mkdir -p "$AGENTS_SKILLS_DIR"
  for name in "${previous[@]}"; do
    [[ -n $name ]] && rm -rf "${AGENTS_SKILLS_DIR:?}/$name"
  done
  for name in "${names[@]}"; do
    cp -R "$tmp/skills/$name" "$AGENTS_SKILLS_DIR/$name"
  done
  printf '%s\n' "${names[@]}" | python3 -I -c 'import json, sys
names = [l for l in sys.stdin.read().splitlines() if l]
json.dump({"source": sys.argv[1], "commit": sys.argv[2], "skills": names}, open(sys.argv[3], "w"), indent=2)' \
    "$PSTACK_MIRROR_URL" "$PSTACK_MIRROR_REF" "$PSTACK_MANIFEST"
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
  [[ $url == */* && $url != *://* && $url != git@* ]] && url="https://github.com/$url.git"
  IDSTACK_SRC="$IDSTACK_CACHE_DIR/src"
  [[ $MODE == dry-run ]] && return
  if [[ -d $IDSTACK_SRC/.git ]]; then
    git -C "$IDSTACK_SRC" pull -q --ff-only
  else
    mkdir -p "$IDSTACK_CACHE_DIR"
    git clone -q "$url" "$IDSTACK_SRC"
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

link_set() {
  # link_set <label> <src dir> <glob> <dest dir>: link matching files, recorded in <dest>/.idstack-install.json
  local label=$1 from=$2 glob=$3 dest=$4 path name linked=()
  if [[ $MODE == dry-run ]]; then
    log "would link $from/$glob into $dest"
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
  # check_set <label> <dest dir>
  if [[ -f $2/.idstack-install.json ]]; then status "$1" ok; else status "$1" absent; fi
}

cli_check() {
  log "idstack CLI"
  if [[ -L $IDSTACK_BIN_DIR/idstack && -x $IDSTACK_BIN_DIR/idstack ]]; then
    status "$IDSTACK_BIN_DIR/idstack" ok
  else
    status "$IDSTACK_BIN_DIR/idstack" absent
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

cli_uninstall() {
  log "idstack CLI"
  local link=$IDSTACK_BIN_DIR/idstack
  [[ -L $link && $(readlink "$link") == */bin/idstack ]] || { log "  no idstack link at $link"; return; }
  # Remove the Codex guard hook first: it calls this binary.
  wants codex && run "$link" guard uninstall --harness codex
  run rm "$link"
}

opencode_check() {
  log "OpenCode"
  if [[ -f $IDSTACK_MANIFEST ]]; then
    status "idstack in $OPENCODE_SKILLS_DIR" ok
  else
    status "idstack in $OPENCODE_SKILLS_DIR" absent
  fi
  check_set "agents in $OPENCODE_AGENTS_DIR" "$OPENCODE_AGENTS_DIR"
}

opencode_install() {
  log "OpenCode ($OPENCODE_SKILLS_DIR)"
  local src name linked=()
  idstack_checkout
  src=$IDSTACK_SRC
  link_set agents "$src/harness/opencode/agents" "*.md" "$OPENCODE_AGENTS_DIR"
  if [[ $MODE == dry-run ]]; then
    log "would link each skill folder under $src/skills into $OPENCODE_SKILLS_DIR"
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
  # models_step [--check|--dry-run|--uninstall]
  [[ $MODELS -eq 1 ]] || return 0
  local args=()
  wants claude && args+=(--target claude)
  if wants codex || wants opencode; then args+=(--target agents); fi
  [[ $FORCE -eq 1 ]] && args+=(--force)
  log "pstack model files"
  python3 -I "$SCRIPT_DIR/scripts/pstack_models.py" "${args[@]}" "$@"
}

main() {
  parse_args "$@"
  need python3 git
  detect_harnesses
  local h
  for h in "${HARNESSES[@]}"; do
    if ! command -v "$h" >/dev/null 2>&1; then
      if [[ $h == opencode ]]; then
        warn "opencode is not on PATH; installing its skills anyway"
      else
        err "$h was requested but its CLI is not on PATH"
        exit 3
      fi
    fi
  done

  log "idstack $MODE for: ${HARNESSES[*]} (source: $SOURCE)"
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
      models_step --check || MISSING=1
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
      if [[ $MODE == dry-run ]]; then models_step --dry-run || FAILED=1; else models_step || FAILED=1; fi
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
      models_step --uninstall
      log "Done. pstack was left in place."
      ;;
  esac
}

main "$@"
