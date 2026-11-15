"""Standard-library invocation isolation, stream validation and log handling."""
import hashlib
import json
import collections
import math
import os
import posixpath
import random
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pricing

USAGE = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
MODEL_USAGE = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "costUSD")
BUNDLED_SKILLS = frozenset({"design", "plugin-authoring"})  # ADR-15 amendment 1: residual skills under disableBundledSkills
BUNDLED_PLUGINS = frozenset({"cc-plugin-agents-md", "cc-plugin-telemetry", "cc-plugin-plugin-authoring"})
TMP_ROOT = Path(r"C:\Users\REDACTED_USER\venvs\token-aware-eval\tmp")
EVAL_ROOT = Path(__file__).resolve().parent.parent
LOG_ROOT = EVAL_ROOT / "logs"


class RunError(RuntimeError):
    pass


class InvocationTimeout(RunError):
    pass


class SkillInputShapeUnconfirmed(RunError):
    def __init__(self, skill_inputs):
        self.skill_inputs = skill_inputs
        super().__init__("Skill tool_use lacks a string input.skill field")


def contained(path, root):
    p, r = Path(path).resolve(), Path(root).resolve()
    if p == r or not p.is_relative_to(r):
        raise RunError("path is outside its allowed root")
    return p


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def tree_hash(root, exclude_credentials=True):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_symlink():
            raise RunError("symlink in controlled directory")
        if p.is_file() and not (exclude_credentials and p.relative_to(root).as_posix() == ".credentials.json"):
            name, data = p.relative_to(root).as_posix().encode(), p.read_bytes()
            h.update(len(name).to_bytes(8,"big")+name+len(data).to_bytes(8,"big")+data)
    return h.hexdigest()


def copy_tree(source, destination):
    source, destination = Path(source), Path(destination)
    for p in source.rglob("*"):
        if p.is_symlink() or not p.resolve().is_relative_to(source.resolve()):
            raise RunError("copy source contains a symlink or escaped path")
        target = destination / p.relative_to(source)
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif p.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)


def skills_from(path):
    if path is None:
        return {}
    result = {}
    for p in sorted(Path(path).glob("*/SKILL.md")):
        name = skill_frontmatter_name(p)
        if name in result:
            raise RunError("duplicate skill name")
        result[name] = p.parent
    return result


def skill_frontmatter_name(path):
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise RunError("skill file has no frontmatter")
    parts = text.split("---",2)
    if len(parts) < 3:
        raise RunError("skill frontmatter is unterminated")
    for line in parts[1].splitlines():
        if line.startswith("name:"):
            name = line.split(":",1)[1].strip().strip("\"'")
            if name:
                return name
    raise RunError("skill frontmatter has no name field")


def fixture_files(path):
    result = {}
    for p in sorted(Path(path).rglob("*")):
        if p.is_file() and "skills" not in p.relative_to(path).parts:
            if p.is_symlink():
                raise RunError("symlink in fixture")
            result[p.relative_to(path).as_posix()] = p.read_bytes()
    return result


def credential_strings(path):
    raw = Path(path).read_text(encoding="utf-8")
    values = [(s, f"line:{index}") for index,s in enumerate(raw.splitlines(),1) if s.strip() and len(s) >= 8]
    def visit(value, path):
        if isinstance(value, str) and len(value) >= 8:
            values.append((value,path or "root"))
        elif isinstance(value, dict):
            for key,v in value.items():
                child = str(key) if not path else path+"."+str(key)
                visit(v,child)
        elif isinstance(value, list):
            for index,v in enumerate(value):
                visit(v,path+f"[{index}]")
    visit(json.loads(raw),"")
    # Check literal strings as well as their JSON-escaped representations.
    needles = {}
    for value,label in values:
        variants = ((value,"literal"),
                    (json.dumps(value,ensure_ascii=False)[1:-1],"json"),
                    (json.dumps(value,ensure_ascii=True)[1:-1],"json-ascii"))
        for variant,suffix in variants:
            needles.setdefault(variant.encode("utf-8"),set()).add(label+":"+suffix)
    return {needle:tuple(sorted(labels)) for needle,labels in needles.items()}


OAUTH_TOKEN_FILE = Path(r"C:\Users\REDACTED_USER\ClaudeHarnessSecrets\oauth-token.txt")  # ADR-16
OAUTH_TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"
# ADR-16: sources that outrank CLAUDE_CODE_OAUTH_TOKEN or reroute requests
# (code.claude.com/docs/en/authentication, "Authentication precedence").
OUTRANKING_ENV = ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
                  "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL")


# ADR-17: credentials-file fields classified non-secret from the r19 hit list
# (run 20261021T083823-a218988d-0001: only claudeAiOauth.rateLimitTier, in ccfg/.claude.json).
NON_SECRET_FIELDS = frozenset({"claudeAiOauth.rateLimitTier"})


def _token_text():
    try:
        return OAUTH_TOKEN_FILE.read_text(encoding="utf-8-sig").strip()
    except (OSError, UnicodeError):
        return ""


def oauth_token():
    token = _token_text()
    if not token:
        raise RunError("OAuth token file unreadable or empty (ADR-16)")
    if len(token) < 8 or any(ch.isspace() for ch in token):
        raise RunError("OAuth token file malformed (ADR-16)")
    return token


def _post_run_needles(cfg):
    """Strings in the run's ccfg\\.credentials.json after the child ran: a token refreshed during the run
    is a needle too (ADR-16 follow-up); labels keep the field paths so ADR-17 still applies."""
    path = Path(cfg)/".credentials.json"
    if not path.is_file():
        return {}
    try:
        return {needle: set(labels) for needle, labels in credential_strings(path).items()}
    except (OSError, UnicodeError, ValueError):
        return {}


def _all_needles(credentials, extra_needles=None):
    needles = {needle: set(labels) for needle, labels in credential_strings(credentials).items()}
    for needle, labels in (extra_needles or {}).items():
        needles.setdefault(needle, set()).update(labels)
    token = _token_text()
    if len(token) >= 8:
        for variant, suffix in ((token, "literal"),
                                (json.dumps(token, ensure_ascii=False)[1:-1], "json"),
                                (json.dumps(token, ensure_ascii=True)[1:-1], "json-ascii")):
            needles.setdefault(variant.encode("utf-8"), set()).add("oauth-token-file:" + suffix)
    # ADR-17: drop a needle only when every label on it names a non-secret field
    return {needle: tuple(sorted(labels)) for needle, labels in needles.items()
            if not all(label.rsplit(":", 1)[0] in NON_SECRET_FIELDS for label in labels)}


def credential_check(paths, credentials, extra_needles=None):
    needles = _all_needles(credentials, extra_needles)
    hits = set()
    for p in paths:
        p = Path(p)
        root = p
        candidates = p.rglob("*") if p.is_dir() else [p]
        prefix = "ccfg" if p.name == "ccfg" else "cwork" if p.name == "cwork" else "log"
        for file in candidates:
            if file.is_file():  # ADR-16 amendment 2: no file in ccfg is exempt
                data = file.read_bytes()
                relative = file.relative_to(root).as_posix() if p.is_dir() else file.name
                for needle,labels in needles.items():
                    if needle in data:
                        for label in labels:
                            hits.add((prefix+"/"+relative,label))
    if hits:
        ordered = sorted(hits)[:50]
        message = "credential exact-string check failed; value withheld; hits="+json.dumps(ordered)
        clean = redact(message.encode("utf-8"),credentials,extra_needles)
        if redact(clean,credentials,extra_needles) != clean:
            raise RunError("credential exact-string check failed; value withheld")
        raise RunError(clean.decode("utf-8"))
    return True


def redact(data, credentials, extra_needles=None):
    for needle in sorted(_all_needles(credentials, extra_needles), key=len, reverse=True):
        data = data.replace(needle, b"<credential-redacted>")
    return data


# ADR-18: Claude Code denied Edit and Write whenever the harness was launched under Codex (RAID I4; r22:
# identical invocation, 2 denials under Codex, 0 from a plain window). Live runs refuse such a launch.
ALLOWED_TOOLS = frozenset({"Read", "Edit", "Write", "Bash", "Skill"})  # ADR-19: the --allowedTools list
RECORDED_OUT_TOOLS = frozenset({"Glob", "Grep"})  # ADR-18 amendment 2: an OUT denial of these is recorded, not voiding
CONFIG_FILES = ("policy-limits.json", "remote-settings.json")  # ADR-21: hashed per record after the child exits
_HOME_TOKEN = re.compile(r"^(?:~|\$HOME|\$\{HOME\}|%USERPROFILE%)(?=$|[\\/])")


def _norm(path):
    p = re.sub(r"^/([a-zA-Z])/", r"\1:/", str(path).replace("\\", "/"))
    return posixpath.normpath(p).lower()


def _inside(target, wd):
    """ADR-19: target made absolute against working_dir (.., ~, $HOME resolved), normalised, case-folded."""
    t = str(target).replace("\\", "/")
    m = _HOME_TOKEN.match(t)
    if m:
        home = re.match(r"^([a-z]:/users/[^/]+)", _norm(wd))
        t = (home.group(1) if home else "/__no_home__") + t[m.end():]
    if not re.match(r"^([A-Za-z]:/|/[a-zA-Z]/)", t):
        t = posixpath.join(str(wd).replace("\\", "/"), t)
    n, w = _norm(t), _norm(wd)
    return n == w or n.startswith(w + "/")


def denial_scope(entry, working_dir):
    """IN (ADR-19): tool on --allowedTools, or no target, or target inside working_dir; else OUT."""
    tool = str(entry.get("tool_name"))
    data = entry.get("tool_input") if isinstance(entry.get("tool_input"), dict) else {}
    target = data.get("file_path") or data.get("path") or data.get("notebook_path")
    if tool in ALLOWED_TOOLS or not target or not working_dir:
        return "IN"
    return "IN" if _inside(target, working_dir) else "OUT"


def launcher_record(environ=None):
    """ADR-21: how the batch was started, recorded at INIT; names and paths only, no environment values."""
    environ = os.environ if environ is None else environ
    return dict(interpreter=sys.executable, argv0=sys.argv[0] if sys.argv else None, cwd=os.getcwd(),
                codex_names=codex_launch_names(environ),
                console_markers={name: name in environ for name in ("WT_SESSION", "SESSIONNAME", "TERM_PROGRAM")})


def config_file_hashes(cfg):
    """ADR-21: md5 of the settings files Claude Code writes into the config directory; null when absent."""
    return {name: (md5(Path(cfg)/name) if (Path(cfg)/name).is_file() else None) for name in CONFIG_FILES}


def codex_launch_names(environ=None):
    environ = os.environ if environ is None else environ
    return sorted(name for name in environ if name.upper().startswith("CODEX_"))


def refuse_codex_launch(environ=None):
    names = codex_launch_names(environ)
    if names:
        raise RunError("I4: launched under Codex (ADR-18); start live runs from a plain cmd window; "
                       "variable names: " + ",".join(names))


def _denial_target(entry):
    tool = str(entry.get("tool_name"))
    data = entry.get("tool_input") if isinstance(entry.get("tool_input"), dict) else {}
    target = data.get("file_path") or data.get("path") or data.get("pattern") or str(data.get("command", ""))[:80]
    return (tool + ":" + str(target))[:160]


def permission_denials(raw, working_dir=None):
    # ADR-18: permission_denied events and the result's permission_denials list (tool and target only),
    # each entry classed IN or OUT by ADR-19 scope (amendments 1 and 2).
    events, listed, tools, targets = 0, 0, set(), set()
    in_count, out_count, out_other, in_targets = 0, 0, 0, []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "system" and event.get("subtype") == "permission_denied":
            events += 1
            tools.add(str(event.get("tool_name")))
        elif event.get("type") == "result":
            entries = [e for e in (event.get("permission_denials") or []) if isinstance(e, dict)]
            listed = len(event.get("permission_denials") or [])
            tools.update(str(e.get("tool_name")) for e in entries)
            targets.update(_denial_target(e) for e in entries)
            in_count, out_count, out_other, in_targets = 0, 0, 0, []
            for e in entries:
                if denial_scope(e, working_dir) == "IN":
                    in_count += 1
                    in_targets.append(_denial_target(e))
                elif str(e.get("tool_name")) in RECORDED_OUT_TOOLS:
                    out_count += 1
                else:
                    out_other += 1
    if events > listed:  # a denial event with no result entry has no target: IN by ADR-19
        in_count += events - listed
    return dict(events=events, result_denials=listed, tools=sorted(tools), targets=sorted(targets)[:20],
                in_count=in_count, out_count=out_count, out_other=out_other, in_targets=sorted(in_targets)[:10])


def child_env(config):
    env = dict(os.environ)
    for name in OUTRANKING_ENV:  # ADR-16
        env.pop(name, None)
    cfg = str(Path(config["temp_root"]) / "ccfg")
    env.update(CLAUDE_CONFIG_DIR=cfg, DISABLE_AUTOUPDATER="1", PYTHONDONTWRITEBYTECODE="1",
               TEMP=config["temp_root"], TMP=config["temp_root"])
    if config.get("git_bash_path"):
        env["CLAUDE_CODE_GIT_BASH_PATH"] = config["git_bash_path"]
    env[OAUTH_TOKEN_ENV] = oauth_token()  # ADR-16: fails closed without the token file
    return env


def _terminate_process_tree(proc):
    if os.name == "nt":
        result = subprocess.run([r"C:\Windows\System32\taskkill.exe", "/PID", str(proc.pid), "/T", "/F"],
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8", errors="replace", timeout=10)
        if result.returncode != 0:
            try:
                proc.kill()
            except OSError:
                pass
    else:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        raise RunError("process tree termination failed") from None
    if proc.poll() is None:
        raise RunError("process tree termination failed")
    return result if os.name == "nt" else None


def child(config, arguments, cwd=None, prompt=None, timeout=900, on_init=None):
    # Claude prompts are arguments; stdin is always closed to prevent a child
    # from waiting on an inherited console or pipe.
    args = list(arguments)
    if prompt is not None:
        try:
            prompt_index = args.index("-p")
        except ValueError:
            raise RunError("prompt supplied without Claude's -p flag")
        args.insert(prompt_index+1,prompt)
    proc = subprocess.Popen(args, cwd=cwd, env=child_env(config), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace")
    stdout_parts, stderr_parts, init_errors = [], [], []

    def read_stdout():
        init_seen = False
        for line in proc.stdout:
            stdout_parts.append(line)
            if on_init is None or init_seen:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "system" and event.get("subtype") == "init":
                init_seen = True
                try:
                    on_init(event)
                except Exception as exc:
                    init_errors.append(exc)
                    _terminate_process_tree(proc)

    def read_stderr():
        stderr_parts.extend(proc.stderr)

    out_thread = threading.Thread(target=read_stdout,daemon=True)
    err_thread = threading.Thread(target=read_stderr,daemon=True)
    out_thread.start()
    err_thread.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(proc)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        out_thread.join(timeout=2)
        err_thread.join(timeout=2)
        raise InvocationTimeout(f"Claude invocation timed out after {timeout} seconds") from None
    out_thread.join(timeout=5)
    err_thread.join(timeout=5)
    result = subprocess.CompletedProcess(args, proc.returncode, "".join(stdout_parts), "".join(stderr_parts))
    result.init_error = init_errors[0] if init_errors else None
    return result


def version(config):
    proc = child(config, [config["claude_binary"], "--version"], timeout=60)
    found = proc.stdout.strip().split(" ",1)[0]
    if proc.returncode or found != config["claude_version"]:
        raise RunError("Claude Code version mismatch; model not called")
    return found


def prepare(config, skills, instruction_files, work_source=None):
    root = Path(config["temp_root"])
    if root.resolve() != TMP_ROOT.resolve():
        raise RunError("temp_root must equal the brief's fixed root")
    root.mkdir(parents=True, exist_ok=True)
    cfg, work = contained(root/"ccfg",root), contained(root/"cwork",root)
    if cfg.exists() or work.exists():
        raise RunError("previous config or working directory is not absent")
    cfg.mkdir()
    work.mkdir()
    for name, source in sorted(skills.items()):
        if not name or Path(name).name != name:
            raise RunError("invalid skill name")
        copy_tree(source, cfg/"skills"/name)
    for rel, data in sorted(instruction_files.items()):
        p = contained(cfg/rel, cfg)
        if p.name == ".credentials.json" or p.relative_to(cfg).parts[0] == "skills":
            raise RunError("instruction file collides with reserved path")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    if work_source:
        copy_tree(work_source, work)
    return cfg, work, tree_hash(cfg)


def cleanup(config):
    root = Path(config["temp_root"])
    if root.resolve() != TMP_ROOT.resolve():
        raise RunError("cleanup root is not the brief's fixed root")
    result = {}
    for name in ("ccfg", "cwork"):
        p = contained(root/name, root)
        if p.is_symlink() or p.is_junction():
            raise RunError("refusing cleanup of linked directory")
        if p.exists():
            shutil.rmtree(p)
        if p.exists():
            raise RunError("directory deletion absence assertion failed")
        result[name+"_absent"] = True
    return result


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or value < 0:
        raise RunError("invalid numeric stream field: "+name)
    return value


def parse_stream(raw, expected_skills, model, trigger_skill=None):
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    counted = collections.Counter(str(e.get("type")) for e in events if isinstance(e, dict))
    event_counts = {key: counted.get(key, 0) for key in ("assistant", "user", "system", "result")}  # ADR-10 amendment 3
    inits = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
    results = [e for e in events if e.get("type") == "result"]
    if len(inits) != 1 or not results:
        raise RunError("missing or duplicate init, or missing final result")
    init, result = inits[0], results[-1]
    observed = init["skills"]
    if not isinstance(observed,list) or not all(isinstance(v,str) for v in observed):
        raise RunError("init skills field is not a string list")
    if set(observed) != set(expected_skills):
        raise RunError("init skill difference: "+json.dumps(dict(extra=sorted(set(observed)-set(expected_skills)), missing=sorted(set(expected_skills)-set(observed)))))
    if init.get("model") != model and model not in result["modelUsage"]:
        raise RunError("full model ID mismatch")
    if init.get("model") and init["model"] != model:
        raise RunError("full init model ID mismatch")
    usage = {key:number(result["usage"][key],key) for key in USAGE}
    cache_creation = result["usage"].get("cache_creation")
    if not isinstance(cache_creation,dict):
        raise RunError("cache write split missing or inconsistent")
    try:
        cache_write_5m = number(cache_creation["ephemeral_5m_input_tokens"],"cache_creation.ephemeral_5m_input_tokens")
        cache_write_1h = number(cache_creation["ephemeral_1h_input_tokens"],"cache_creation.ephemeral_1h_input_tokens")
    except (KeyError,RunError):
        raise RunError("cache write split missing or inconsistent") from None
    if cache_write_5m + cache_write_1h != usage["cache_creation_input_tokens"]:
        raise RunError("cache write split missing or inconsistent")
    mixes = result["modelUsage"]
    if not mixes:
        raise RunError("empty modelUsage")
    for name, fields in mixes.items():
        for key in MODEL_USAGE:
            number(fields[key], name+"."+key)
    skill_calls = []
    triggered = False
    for event in events:
        if event.get("type") == "assistant":
            for block in event["message"]["content"]:
                if block.get("type") == "tool_use" and block.get("name") == "Skill":
                    raw_input = block.get("input")
                    skill_calls.append(raw_input)
                    if not isinstance(raw_input,dict) or not isinstance(raw_input.get("skill"),str):
                        raise SkillInputShapeUnconfirmed(skill_calls)
                    if trigger_skill and raw_input["skill"] == trigger_skill:
                        triggered = True
    if result["is_error"]:
        raise RunError("Claude result is_error")
    return dict(observed_skills=sorted(observed), usage=usage,
                cache_write_5m=cache_write_5m, cache_write_1h=cache_write_1h,
                total_cost_usd=number(result["total_cost_usd"],"total_cost_usd"),
                modelUsage=mixes, turn_count=number(result["num_turns"],"num_turns"),
                duration_ms=number(result["duration_ms"],"duration_ms"),
                triggered=triggered, skill_calls=skill_calls, event_counts=event_counts,
                auxiliary_models={name:{key:number(fields[key],name+"."+key) for key in ("inputTokens","outputTokens","cacheReadInputTokens","cacheCreationInputTokens")}
                                  for name,fields in mixes.items() if name != model},
                response=result.get("result",""))


def validate_init(init, expected_skills, shell_tool, expected_tools):
    observed_skills = init.get("skills")
    if not isinstance(observed_skills,list) or not all(isinstance(v,str) for v in observed_skills):
        raise RunError("init skills field is not a string list")
    if any(name.startswith("anthropic-skills:") for name in observed_skills):
        raise RunError("init skill uses forbidden anthropic-skills namespace")
    expected = set(expected_skills) | BUNDLED_SKILLS
    if set(observed_skills) != expected:
        raise RunError("init skill difference: "+json.dumps(dict(
            extra=sorted(set(observed_skills)-expected), missing=sorted(expected-set(observed_skills)))))
    plugins = init.get("plugins")
    if not isinstance(plugins,list):
        raise RunError("init.plugins is not a list")
    names = [p.get("name") for p in plugins if isinstance(p,dict)]
    if len(names) != len(plugins) or set(names) != BUNDLED_PLUGINS or any(p.get("path") != "builtin" for p in plugins):
        raise RunError("init plugin set or path differs from the pinned built-ins")
    servers = init.get("mcp_servers")
    if not isinstance(servers,list) or servers:
        raise RunError("init.mcp_servers is not empty")
    observed_tools = init.get("tools")
    if not isinstance(observed_tools,list) or not all(isinstance(t,str) for t in observed_tools):
        raise RunError("init.tools is not a list of tool names")
    if shell_tool and shell_tool not in observed_tools:
        raise RunError("configured shell tool absent from init.tools")
    if any(t in observed_tools for t in ("WebFetch","WebSearch")):
        raise RunError("web tool unexpectedly present in init.tools")
    other_shell = "PowerShell" if shell_tool == "Bash" else "Bash"
    if shell_tool and other_shell in observed_tools:
        raise RunError("unconfigured shell unexpectedly present in init.tools")
    if expected_tools and set(observed_tools) != set(expected_tools):
        raise RunError("init.tools differs from configured tool set")
    return dict(skills=sorted(observed_skills),plugins=plugins,mcp_servers=servers,tools=observed_tools)


def block_order(arms, rounds, seed):
    rng = random.Random(seed)
    result = []
    for round_id in range(rounds):
        order = list(arms)
        rng.shuffle(order)
        result.extend((round_id, position, arm) for position,arm in enumerate(order))
    return result


def tokens(record):
    return sum(record["usage"][k] for k in USAGE if k != "output_tokens")


def claude_arguments(config):
    return [config["claude_binary"], "--settings", '{"syncClaudeAiSkills":false,"disableBundledSkills":true,"skillOverrides":{"doctor":"off"}}',
            "-p", "--output-format", "stream-json", "--verbose", "--model", config["model_id"]] + config["permission_flags"]


class Runner:
    def __init__(self, config, batch_id=None, log_dir=None):
        refuse_codex_launch()  # ADR-18
        self.config = json.loads(json.dumps(config))
        self.permission_flags = tuple(config["permission_flags"])
        self.tool_set = tuple(config.get("tool_set", []))
        self.observed_tool_set = None
        self.batch_id = batch_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
        self.logs = Path(log_dir or config["log_root"]).resolve()
        if self.logs != LOG_ROOT.resolve():
            contained(self.logs, LOG_ROOT)
        self.logs.mkdir(parents=True, exist_ok=True)
        self.previous, self.records, self.flagged, self.packed = {}, [], 0, set()
        self.launcher = launcher_record()  # ADR-21
        version(config)  # batch assertion, separate from every invocation assertion

    def invoke(self, prompt, skills, files, track, item, arm, work_source=None, check=None, metadata=None, snapshot=None):
        refuse_codex_launch()  # ADR-18
        c = self.config
        run_id = self.batch_id+"-"+f"{len(self.records)+1:04d}"
        raw_path, err_path, rec_path = [self.logs/(run_id+suffix) for suffix in (".stream.jsonl", ".stderr.txt", ".record.json")]
        start = time.time()
        key = (item, arm)
        rec = dict(run_id=run_id, track=track, batch_id=self.batch_id, task_or_fixture_id=item, arm=arm,
                   model_id=c["model_id"], claude_version=c["claude_version"], harness_md5=md5(Path(__file__).with_name("harness.py")),
                   seed=c["seed"], round=0, position=0, start_time=datetime.now(timezone.utc).isoformat(),
                   gap_since_previous_same_arm=start-self.previous[key] if key in self.previous else None,
                   config_dir=str(Path(c["temp_root"])/"ccfg"), working_dir=str(Path(c["temp_root"])/"cwork"),
                   expected_skills=sorted(set(skills)|BUNDLED_SKILLS), flags=[], check_exit_code=None, check_reason=None,
                   credential_check=False, deletion_assertions={},
                   shell_tool=c.get("shell_tool"), configured_tool_set=list(self.tool_set),
                   permission_flags=list(self.permission_flags), containment="UNVERIFIED",
                   observed_tools=None, observed_plugins=None, observed_mcp_servers=None,
                   skill_calls=[], shell_tool_confirmed=False, auxiliary_models={}, temp_leftovers=[],
                   permission_denials=None, launcher=self.launcher, config_files=None, event_counts=None)
        rec["runlib_md5"] = md5(Path(__file__))
        rec["pricing_md5"] = md5(Path(pricing.__file__))
        if metadata:
            rec.update(metadata)
        self.previous[key] = start
        failure = None
        owned = False
        post_needles = {}
        temp_before = _temp_entries(c["temp_root"])
        try:
            if tuple(c["permission_flags"]) != self.permission_flags or tuple(c.get("tool_set",[])) != self.tool_set:
                raise RunError("configured tool set changed within batch")
            version(c)
            cfg = Path(c["temp_root"])/"ccfg"
            work = Path(c["temp_root"])/"cwork"
            if cfg.exists() or work.exists():
                raise RunError("controlled directories already exist")
            owned = True
            cfg, work, rec["config_dir_hash"] = prepare(c,skills,files,work_source)
            args = claude_arguments(c)
            rec["command"] = args
            init_count = 0
            def check_init(event):
                nonlocal init_count
                init_count += 1
                if init_count != 1:
                    raise RunError("duplicate init event")
                rec["observed_skills"] = event.get("skills")
                rec["observed_plugins"] = event.get("plugins")
                rec["observed_mcp_servers"] = event.get("mcp_servers")
                rec["observed_tools"] = event.get("tools")
                checked = validate_init(event,skills.keys(),c.get("shell_tool"),self.tool_set)
                rec["observed_skills"] = checked["skills"]
                rec["observed_plugins"] = checked["plugins"]
                rec["observed_mcp_servers"] = checked["mcp_servers"]
                rec["observed_tools"] = checked["tools"]
                rec["shell_tool_confirmed"] = bool(c.get("shell_tool"))
                current = tuple(sorted(checked["tools"]))
                if self.observed_tool_set is not None and current != self.observed_tool_set:
                    raise RunError("observed tool set changed within batch")
                self.observed_tool_set = current
            proc = child(c,args,cwd=str(work),prompt=prompt,on_init=check_init)
            post_needles = _post_run_needles(cfg)
            rec["config_files"] = config_file_hashes(cfg)  # ADR-21
            raw_bytes, err_bytes = proc.stdout.encode(), proc.stderr.encode()
            clean_raw, clean_err = redact(raw_bytes,c["credentials_file"],post_needles), redact(err_bytes,c["credentials_file"],post_needles)
            raw_path.write_bytes(clean_raw)
            err_path.write_bytes(clean_err)
            if clean_raw != raw_bytes or clean_err != err_bytes:
                raise RunError("credential exact-string check failed; output redacted")
            if getattr(proc,"init_error",None):
                raise RunError(str(proc.init_error))
            if c.get("shell_tool") and init_count != 1:
                raise RunError("cannot confirm shell tool: expected one init event")
            if proc.returncode:
                raise RunError("Claude subprocess exited "+str(proc.returncode))
            trigger_skill = skill_frontmatter_name(Path(c["token_skill_root"])/"SKILL.md") if c.get("token_skill_root") else None
            rec.update(parse_stream(proc.stdout,set(skills)|BUNDLED_SKILLS,c["model_id"],trigger_skill))
            if track == "A" and rec.get("triple") is not None and rec.get("turn_count") != 1:
                rec["flags"].append("multi_turn_triple")
                rec["error"] = "multi_turn_triple"
                failure = RunError("multi_turn_triple")
            elif track == "A" and rec.get("triple") is not None and (rec["event_counts"]["assistant"] > 1 or rec["event_counts"]["result"] > 1):
                rec["flags"].append("multi_request_triple")  # ADR-10 amendment 3
                rec["error"] = "multi_request_triple"
                failure = RunError("multi_request_triple")
            rec["permission_denials"] = permission_denials(proc.stdout, rec["working_dir"])  # ADR-18, ADR-19 scope
            denied = rec["permission_denials"]
            if denied["in_count"] or denied["out_other"]:
                rec["flags"].append("permission_denied")  # void; analysis excludes it (harness.valid)
            if denied["in_count"]:
                rec["error"] = "IN permission denial (%s); batch stopped (ADR-18 amendment 1)" % ", ".join(denied["in_targets"][:5])
                failure = RunError(rec["error"])
            rec["auxiliary_models"] = rec.get("auxiliary_models", {})
            if rec["auxiliary_models"]:
                rec["flags"].append("auxiliary_model")
            rec.update(pricing.assert_cost(rec["modelUsage"],rec["total_cost_usd"],c["pricing_tools"],c.get("rates_path"),
                                           cache_write_5m=rec["cache_write_5m"],cache_write_1h=rec["cache_write_1h"]))
            total = tokens(rec)
            rec["cache_read_share"] = rec["usage"]["cache_read_input_tokens"]/total if total else 0.0
            if rec["cost_flagged"]:
                rec["flags"].append("cost_assertion")
                self.flagged += 1
                if self.flagged > c["cost_assertion_cap"]:
                    raise RunError("cost assertion cap exceeded; run excluded from every endpoint")
            if check:
                checked = child(c,[sys.executable,"-B","-I",str(check),str(work)],cwd=str(work),timeout=60)
                reason = redact((checked.stdout+checked.stderr).encode(),c["credentials_file"],post_needles).decode()
                rec.update(check_exit_code=checked.returncode,check_reason=reason)
            if snapshot:
                snapshot(work, cfg)
            credential_check([cfg,work,raw_path,err_path],c["credentials_file"],post_needles)
            rec["credential_check"] = True
        except Exception as exc:
            failure = exc
            if isinstance(exc, SkillInputShapeUnconfirmed):
                rec["skill_calls"] = exc.skill_inputs
                rec["flags"].append("skill_input_shape_unconfirmed")
            else:
                rec["flags"].append("timeout" if isinstance(exc, InvocationTimeout) else type(exc).__name__)
            rec["error"] = redact(str(exc).encode(),c["credentials_file"],post_needles).decode()
        finally:
            temp_after = _temp_entries(c["temp_root"])
            rec["temp_leftovers"] = sorted(temp_after-temp_before)
            if owned:
                try:
                    rec["deletion_assertions"] = cleanup(c)
                except Exception as exc:
                    failure = exc
                    rec["flags"].append("cleanup_failed")
                    rec["cleanup_error"] = type(exc).__name__
            # A record must be credential-free before it is persisted.
            serial = json.dumps(rec, sort_keys=True, indent=2, allow_nan=False).encode()
            clean = redact(serial,c["credentials_file"],post_needles)
            if clean != serial:
                failure = RunError("credential found in record; redacted")
                rec["credential_check"] = False
                rec["flags"].append("credential_record_failed")
                clean = redact(json.dumps(rec,sort_keys=True,indent=2).encode(),c["credentials_file"],post_needles)
            rec_path.write_bytes(clean+b"\n")
            self.records.append(rec)
        print(json.dumps(dict(run_id=run_id, flags=rec["flags"], record=str(rec_path)),sort_keys=True),flush=True)
        if len(self.records) % 500 == 0:
            self.checkpoint()
        if failure:
            raise RunError(rec.get("error",str(type(failure).__name__))) from None
        if "multi_turn_triple" in rec["flags"]:
            raise RunError("multi_turn_triple")
        if "multi_request_triple" in rec["flags"]:
            raise RunError("multi_request_triple")
        return rec

    def checkpoint(self):
        paths = [p for p in sorted(self.logs.glob(self.batch_id+"*")) if p.is_file() and p.suffix != ".gz" and p.name not in self.packed]
        credential_check(paths,self.config["credentials_file"])
        # Bound uncompressed payload to 28 MiB, leaving ample gzip/tar overhead.
        limit = 28*1024*1024
        entries, size, archives = [], 0, []
        def flush():
            nonlocal entries,size
            if not entries:
                return
            part = self.logs/(self.batch_id+"-part-"+uuid.uuid4().hex[:12]+".tar.gz")
            with tarfile.open(part,"w:gz") as tar:
                for name,data in entries:
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    info.mtime = 0
                    tar.addfile(info,BytesIO(data))
            if part.stat().st_size > 30*1024*1024:
                raise RunError("checkpoint exceeds 30 MiB")
            archives.append(str(part))
            entries,size = [],0
        for p in paths:
            data = p.read_bytes()
            for offset in range(0,max(1,len(data)),limit):
                chunk = data[offset:offset+limit]
                if size+len(chunk) > limit:
                    flush()
                entries.append((p.name if len(data)<=limit else p.name+f".chunk-{offset//limit:04d}",chunk))
                size += len(chunk)
            self.packed.add(p.name)
        flush()
        print(json.dumps(dict(invocations=len(self.records),flagged=self.flagged,archives=archives),sort_keys=True),flush=True)


def _temp_entries(root):
    root = Path(root)
    if not root.exists():
        return set()
    excluded = {"ccfg", "cwork", "pytest"}
    return {p.name for p in root.iterdir() if p.name not in excluded and not p.name.startswith("step")}
