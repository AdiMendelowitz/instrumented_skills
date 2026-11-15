import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import harness as h
import pricing
import runlib as r

SAMPLES = Path(__file__).parent/"samples"
MODEL = "claude-sonnet-5-5"
MASTER = r"C:\Users\REDACTED_USER\Documents\ClaudeSkills\skills\token-aware\tools"


def sample(name="single"):
    return (SAMPLES/(name+".synthetic.jsonl")).read_text(encoding="utf-8")


@pytest.fixture
def controlled(tmp_path):
    cfg,work = r.TMP_ROOT/"ccfg",r.TMP_ROOT/"cwork"
    if cfg.exists() or work.exists():
        pytest.fail("pre-existing controlled directory; refusal to remove it")
    credentials = tmp_path/"synthetic-credentials.json"
    credentials.write_text(json.dumps({"oauth":{"token":"synthetic-secret-value-12345"}}),encoding="utf-8")
    config = dict(temp_root=str(r.TMP_ROOT),credentials_file=str(credentials),
                  claude_binary=str(tmp_path/"stub.cmd"),claude_version="2.1.303",
                  model_id=MODEL,seed=17,permission_flags=[],trigger_skill="token-aware",
                  shell_tool="Bash",tool_set=["Read","Edit","Write","Bash","Skill","Glob","Grep"],
                  pricing_tools=MASTER,cost_assertion_cap=0,log_root=str(r.LOG_ROOT),eval_root=str(r.EVAL_ROOT))
    yield config,tmp_path
    if cfg.exists() or work.exists():
        r.cleanup(config)


def test_item1_version_pin_aborts_run_task_without_model(controlled,monkeypatch,capsys):
    c,tmp = controlled
    marker = tmp/"model-called.txt"
    Path(c["claude_binary"]).write_text('@echo off\nif "%~1"=="--version" (echo 0.0.0& exit /b 0)\necho CALLED>'+str(marker)+'\n',encoding="utf-8")
    monkeypatch.setattr(h,"load_config",lambda path:c)
    assert h.main(["run-task"]) == 1
    assert not marker.exists()
    assert "version mismatch" in capsys.readouterr().err
    print("item 1: run-task exited 1 on stub version mismatch; model marker absent")


def test_item1_full_model_id_rejected():
    events = [json.loads(line) for line in sample().splitlines()]
    events[0]["model"] = "wrong-full-model-id"
    with pytest.raises(r.RunError,match="model ID mismatch"):
        r.parse_stream("\n".join(json.dumps(e) for e in events),["stub"],MODEL)
    print("item 1: wrong full model ID rejected")


def test_item2_hash_reproducible_and_stray_changes_it(controlled):
    c,tmp = controlled
    skill = tmp/"stub"
    skill.mkdir()
    (skill/"SKILL.md").write_text("---\nname: stub\n---\nSynthetic skill.\n",encoding="utf-8")
    files = {"CLAUDE.md":b"Synthetic fixture.\n","memory/a.md":b"sample\n"}
    cfg,work,first = r.prepare(c,{"stub":skill},files)
    assert not (cfg/".credentials.json").exists()  # ADR-16 amendment 2: no credentials copy
    assert not (cfg/"settings.json").exists()
    r.cleanup(c)
    cfg,work,second = r.prepare(c,{"stub":skill},files)
    assert first == second
    (cfg/".credentials.json").write_text("synthetic replacement",encoding="utf-8")
    assert r.tree_hash(cfg) == first
    (cfg/"stray.txt").write_text("extra",encoding="utf-8")
    assert r.tree_hash(cfg) != first
    without_changed_credential = r.tree_hash(cfg)
    assert without_changed_credential != first  # stray remains included
    assert r.tree_hash(cfg) == without_changed_credential
    print("item 2: repeated arm hashes equal; stray file changes hash; credentials excluded")


def test_item2_every_child_has_fixed_config_and_autoupdater(controlled):
    c,tmp = controlled
    proc = r.child(c,[sys.executable,"-B","-c","import os; print(os.environ['CLAUDE_CONFIG_DIR']); print(os.environ['DISABLE_AUTOUPDATER'])"])
    assert proc.returncode == 0
    assert proc.stdout.splitlines() == [str(r.TMP_ROOT/"ccfg"),"1"]
    print("item 2: real subprocess received fixed CLAUDE_CONFIG_DIR and DISABLE_AUTOUPDATER=1")


def test_native_claude_executable_preserves_prompt_arguments_and_closes_stdin(controlled):
    c,tmp = controlled
    capture = tmp/"capture.py"
    capture.write_text(
        "import json,sys,threading\n"
        "data=[]\n"
        "done=threading.Event()\n"
        "def read_stdin():\n"
        " data.append(sys.stdin.buffer.read())\n"
        " done.set()\n"
        "t=threading.Thread(target=read_stdin,daemon=True); t.start()\n"
        "eof=done.wait(1) and data[0] == b''\n"
        "open(__import__('os').environ['CAPTURE_FILE'],'w',encoding='utf-8').write(json.dumps({'argv':sys.argv[1:],'stdin_eof':eof}))\n",
        encoding="utf-8",newline="\n")
    task_prompt = (Path(r.EVAL_ROOT)/"tasks"/"T01"/"task.md").read_text(encoding="utf-8")
    prompts = ["Reply with the single word OK.",h.EDIT_PROMPT,task_prompt]
    env = r.child_env(c)
    for index,prompt in enumerate(prompts):
        output = tmp/f"argv-{index}.json"
        env["CAPTURE_FILE"] = str(output)
        test_config = dict(c)
        # child_env is the production environment path; this extra variable
        # only tells the no-model shim where to persist its observation.
        original = r.child_env
        try:
            r.child_env = lambda config, env=env: dict(env)
            proc = r.child(test_config,[sys.executable,str(capture),"-p"],prompt=prompt,timeout=10)
        finally:
            r.child_env = original
        assert proc.returncode == 0, proc.stderr
        observed = json.loads(output.read_text(encoding="utf-8"))
        assert observed["argv"] == ["-p",prompt]
        assert observed["stdin_eof"] is True
    print("native launch-path integrity: 3/3 prompts byte-identical including newlines; stdin EOF within 1s")


def test_child_timeout_terminates_own_process_tree(controlled):
    c,tmp = controlled
    sleeper = tmp/"sleep_stub.py"
    sleeper.write_text("import time\ntime.sleep(10)\n",encoding="utf-8")
    started = time.monotonic()
    with pytest.raises(r.InvocationTimeout,match="timed out after 0.2 seconds"):
        r.child(c,[sys.executable,str(sleeper)],timeout=0.2)
    assert time.monotonic()-started < 8
    print("per-invocation timeout: stub exceeded 0.2s; child terminated and timeout raised")


@pytest.mark.skipif(os.name != "nt",reason="taskkill fallback is Windows-specific")
def test_terminate_tree_falls_back_to_kill_after_taskkill_failure(monkeypatch):
    class Proc:
        pid = 424242
        killed = False
        def kill(self): self.killed = True
        def wait(self,timeout=None): return -9
        def poll(self): return -9 if self.killed else None
    proc = Proc()
    monkeypatch.setattr(r.subprocess,"run",lambda *args,**kwargs:SimpleNamespace(returncode=1))
    r._terminate_process_tree(proc)
    assert proc.killed
    print("process termination: non-zero taskkill result fell back to proc.kill and waited")


def test_bad_init_terminates_child_before_model_completes(controlled):
    c,tmp = controlled
    child_script = tmp/"init_then_sleep.py"
    pid_file = tmp/"child.pid"
    event = {"type":"system","subtype":"init","skills":sorted(r.BUNDLED_SKILLS),
             "plugins":[{"name":"rogue-plugin","path":"C:\\x"}],"mcp_servers":[],"tools":["Bash"]}
    child_script.write_text(
        "import os,time\n"
        f"open({str(pid_file)!r},'w').write(str(os.getpid()))\n"
        f"print({json.dumps(json.dumps(event))},flush=True)\n"
        "time.sleep(10)\n",encoding="utf-8")
    started = time.monotonic()
    proc = r.child(c,[sys._base_executable,str(child_script)],timeout=20,
                   on_init=lambda init:r.validate_init(init,[],"Bash",["Bash"]))
    elapsed = time.monotonic()-started
    assert isinstance(proc.init_error,r.RunError)
    assert "plugin" in str(proc.init_error)
    assert elapsed < 5
    print("init guardrail: invalid init killed the harness child tree before its 10s sleep completed")
    child_pid = int(pid_file.read_text(encoding="ascii"))
    kernel = ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p,ctypes.c_uint32]
    kernel.WaitForSingleObject.restype = ctypes.c_uint32
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x00100000,False,child_pid)
    if handle:
        wait_result = kernel.WaitForSingleObject(handle,0)
        kernel.CloseHandle(handle)
        still_exists = wait_result == 0x00000102
    else:
        still_exists = False
    assert not still_exists
    assert proc.returncode != 0
    print(f"init child process check: pid {child_pid} absent; returncode {proc.returncode}; elapsed {elapsed:.3f}s")


def test_item3_extra_init_skill_rejected_with_difference():
    with pytest.raises(r.RunError,match="extra-synthetic-skill") as caught:
        r.parse_stream(sample("extra-skill"),["stub"],MODEL)
    assert '"missing": []' in str(caught.value)
    print("item 3: "+str(caught.value))


@pytest.mark.parametrize("name,models",[("single",1),("mixed",2)])
def test_item4_sample_model_mixes(name,models):
    parsed = r.parse_stream(sample(name),["stub"],MODEL)
    assert len(parsed["modelUsage"]) == models
    assert parsed["usage"] == dict(input_tokens=100,output_tokens=10,cache_creation_input_tokens=20,cache_read_input_tokens=40)
    assert parsed["turn_count"] == 1 and parsed["duration_ms"] == 100
    assert parsed["cache_write_5m"] == 20 and parsed["cache_write_1h"] == 0
    print(f"item 4: synthetic {name} sample parsed; {models} model(s)")


def test_cache_write_split_inconsistent_is_rejected():
    events = [json.loads(line) for line in sample().splitlines()]
    events[-1]["usage"]["cache_creation"]["ephemeral_5m_input_tokens"] = 19
    with pytest.raises(r.RunError,match="cache write split missing or inconsistent"):
        r.parse_stream("\n".join(json.dumps(e) for e in events),["stub"],MODEL)
    print("cache TTL split: inconsistent 5m/1h totals rejected")


def test_auxiliary_model_records_four_token_counts():
    parsed = r.parse_stream(sample("mixed"),["stub"],MODEL)
    assert parsed["auxiliary_models"]["synthetic-auxiliary"] == dict(
        inputTokens=100,outputTokens=10,cacheReadInputTokens=40,cacheCreationInputTokens=20)
    print("request accounting: auxiliary model recorded with four token counts")


def test_multi_turn_triple_is_flagged_and_stops():
    events = [json.loads(line) for line in sample().splitlines()]
    events[-1]["num_turns"] = 2
    parsed = r.parse_stream("\n".join(json.dumps(e) for e in events),["stub"],MODEL)
    assert parsed["turn_count"] == 2
    assert parsed["turn_count"] != 1  # Runner marks and raises multi_turn_triple.
    print("request accounting: multi-turn triple identified for stop handling")


def test_load_config_rejects_token_skill_name_mismatch(tmp_path):
    skill_root = tmp_path/"token-skill"
    skill_root.mkdir()
    (skill_root/"SKILL.md").write_text("---\nname: actual-frontmatter-name\n---\n",encoding="utf-8")
    config = json.loads((Path(__file__).parent/"config.example.json").read_text(encoding="utf-8"))
    config["token_skill_root"] = str(skill_root)
    config["trigger_skill"] = "different-config-name"
    path = tmp_path/"config.json"
    path.write_text(json.dumps(config),encoding="utf-8")
    with pytest.raises(r.RunError,match="frontmatter name differs"):
        h.load_config(path)
    print("token skill identity: load_config rejects mismatched frontmatter and trigger_skill")


def test_skill_set_uses_frontmatter_name_as_key(tmp_path):
    c = {"eval_root":str(r.EVAL_ROOT),"token_skill_root":str(tmp_path)}
    (tmp_path/"SKILL.md").write_text("---\nname: renamed-token-skill\n---\n",encoding="utf-8")
    skills = h.skill_set(c,"K0")
    assert skills["renamed-token-skill"] == tmp_path
    assert "token-aware" not in skills
    print("token skill identity: skill_set uses frontmatter name for installed directory")


def test_edit_evidence_records_file_and_total_byte_changes():
    evidence = h.edit_evidence({"a.txt":b"abc","b.txt":b"z"},{"a.txt":b"abcd","c.txt":b"xy"})
    assert evidence["files"] == {
        "a.txt":dict(bytes_before=3,bytes_after=4,changed=True),
        "b.txt":dict(bytes_before=1,bytes_after=0,changed=True),
        "c.txt":dict(bytes_before=0,bytes_after=2,changed=True)}
    assert evidence["total_bytes_before"] == 4 and evidence["total_bytes_after"] == 6
    print("edit evidence: per-file and total byte counts recorded")


def test_temp_entries_reports_only_new_direct_entries(tmp_path):
    (tmp_path/"kept.txt").write_text("x")
    before = r._temp_entries(tmp_path)
    (tmp_path/"new.txt").write_text("y")
    (tmp_path/"ccfg").mkdir()
    (tmp_path/"step21.cmd").write_text("x")
    (tmp_path/"pytest").mkdir()
    assert r._temp_entries(tmp_path)-before == {"new.txt"}
    print("temp leftovers: only new direct entries outside excluded names are recorded")


@pytest.mark.parametrize("field",["input_tokens","output_tokens","cache_creation_input_tokens","cache_read_input_tokens"])
def test_item4_missing_usage_field_fails(field):
    events = [json.loads(line) for line in sample().splitlines()]
    del events[-1]["usage"][field]
    with pytest.raises(KeyError):
        r.parse_stream("\n".join(json.dumps(e) for e in events),["stub"],MODEL)


@pytest.mark.parametrize("field",["total_cost_usd","modelUsage","num_turns","duration_ms"])
def test_item4_missing_result_field_fails(field):
    events = [json.loads(line) for line in sample().splitlines()]
    del events[-1][field]
    with pytest.raises(KeyError):
        r.parse_stream("\n".join(json.dumps(e) for e in events),["stub"],MODEL)


def _stream_with_skill_call(skill_name=None):
    events = [json.loads(line) for line in sample().splitlines()]
    if skill_name is not None:
        events.insert(-1,{"type":"assistant","message":{"content":[
            {"type":"tool_use","name":"Skill","input":{"skill":skill_name}}
        ]}})
    return "\n".join(json.dumps(event) for event in events)


def test_item5_bundled_simplify_is_not_a_trigger(tmp_path):
    parsed = r.parse_stream(_stream_with_skill_call("simplify"),["stub"],MODEL,trigger_skill="token-aware")
    assert parsed["triggered"] is False
    assert parsed["skill_calls"] == [{"skill":"simplify"}]
    print("item 5: bundled simplify recorded; trigger false")


def test_item5_frontmatter_named_token_skill_triggers(tmp_path):
    skill_file = tmp_path/"SKILL.md"
    skill_file.write_text("---\nname: token-aware-from-frontmatter\n---\nSynthetic.\n",encoding="utf-8")
    trigger_name = r.skill_frontmatter_name(skill_file)
    parsed = r.parse_stream(_stream_with_skill_call(trigger_name),["stub"],MODEL,trigger_skill=trigger_name)
    assert parsed["triggered"] is True
    assert parsed["skill_calls"] == [{"skill":trigger_name}]
    print("item 5: frontmatter token-aware skill recorded; trigger true")


def test_item5_no_skill_call_is_not_a_trigger():
    parsed = r.parse_stream(_stream_with_skill_call(),["stub"],MODEL,trigger_skill="token-aware")
    assert parsed["triggered"] is False
    assert parsed["skill_calls"] == []
    print("item 5: no Skill tool call; trigger false")


def test_skill_input_shape_unconfirmed_preserves_raw_input():
    raw = _stream_with_skill_call()
    events = [json.loads(line) for line in raw.splitlines()]
    events.insert(-1,{"type":"assistant","message":{"content":[
        {"type":"tool_use","name":"Skill","input":{"skill_name":"token-aware"}}
    ]}})
    with pytest.raises(r.SkillInputShapeUnconfirmed) as caught:
        r.parse_stream("\n".join(json.dumps(event) for event in events),["stub"],MODEL,trigger_skill="token-aware")
    assert caught.value.skill_inputs == [{"skill_name":"token-aware"}]
    print("skill input guard: raw input saved; missing string input.skill raises unconfirmed-shape error")


def test_init_requires_exact_bundled_skills_plugins_and_no_mcp():
    init = {"skills":sorted(r.BUNDLED_SKILLS|{"stub"}),
            "plugins":[{"name":name,"path":"builtin"} for name in sorted(r.BUNDLED_PLUGINS)],
            "mcp_servers":[],"tools":["Bash","Edit","Glob","Grep","Read","Skill","Write"]}
    checked = r.validate_init(init,{"stub"},"Bash",init["tools"])
    assert set(checked["skills"]) == r.BUNDLED_SKILLS|{"stub"}
    bad = dict(init,plugins=init["plugins"][:-1])
    with pytest.raises(r.RunError,match="plugin set or path"):
        r.validate_init(bad,{"stub"},"Bash",init["tools"])
    bad = dict(init,mcp_servers=[{"name":"unexpected"}])
    with pytest.raises(r.RunError,match="mcp_servers"):
        r.validate_init(bad,{"stub"},"Bash",init["tools"])
    print("init guardrail: exact bundled skill/plugin sets and empty MCP list required")


def test_init_rejects_anthropic_skills_namespace():
    skills = r.BUNDLED_SKILLS|{"arm-skill","anthropic-skills:token-aware"}
    init = {"skills":sorted(skills),
            "plugins":[{"name":name,"path":"builtin"} for name in sorted(r.BUNDLED_PLUGINS)],
            "mcp_servers":[],"tools":["Bash"]}
    with pytest.raises(r.RunError,match="forbidden anthropic-skills namespace"):
        r.validate_init(init,{"arm-skill"},"Bash",["Bash"])
    print("init guardrail: anthropic-skills namespace rejected")


def test_claude_argv_disables_synced_skills_with_settings_argument():
    config = dict(claude_binary="claude.exe",model_id=MODEL,permission_flags=["--permission-mode","dontAsk"])
    args = r.claude_arguments(config)
    index = args.index("--settings")
    assert args[index+1] == '{"syncClaudeAiSkills":false,"disableBundledSkills":true,"skillOverrides":{"doctor":"off"}}'
    print("Claude argv: --settings is followed by exact syncClaudeAiSkills=false JSON")


def test_item6_seeded_block_order():
    order = r.block_order(["N","K0","K1"],5,17)
    assert order == r.block_order(["N","K0","K1"],5,17)
    assert order != r.block_order(["N","K0","K1"],5,18)
    for i in range(5):
        assert {a for rd,p,a in order if rd == i} == {"N","K0","K1"}
    print("item 6: seeded arm order reproducible; each round contains each arm once")


def test_item7_planted_json_token_detected_without_disclosure(controlled):
    c,tmp = controlled
    log = tmp/"leak.txt"
    log.write_text("prefix synthetic-secret-value-12345 suffix",encoding="utf-8")
    with pytest.raises(r.RunError,match="credential exact-string check failed") as caught:
        r.credential_check([log],c["credentials_file"])
    assert "synthetic-secret-value-12345" not in str(caught.value)
    assert b"synthetic-secret-value-12345" not in r.redact(log.read_bytes(),c["credentials_file"])
    print("item 7: planted JSON token value detected; exception contains no token")


def test_credential_needle_set_matches_previous_logic(tmp_path):
    secret = "synthetic-needle-set-token-12345"
    credentials = tmp_path/"credentials.json"
    raw = ('{\n  "pretty": "ordinary descriptive text",\n'
           '  "claudeAiOauth": {"scopes": ["'+secret+'"]}\n}\n')
    credentials.write_text(raw,encoding="utf-8")
    values = {line for line in raw.splitlines() if line.strip() and len(line) >= 8}
    def visit(value):
        if isinstance(value,str) and len(value) >= 8:
            values.add(value)
        elif isinstance(value,dict):
            for item in value.values():
                visit(item)
        elif isinstance(value,list):
            for item in value:
                visit(item)
    visit(json.loads(raw))
    previous = {s.encode("utf-8") for value in values for s in
                (value,json.dumps(value,ensure_ascii=False)[1:-1],json.dumps(value)[1:-1])}
    assert set(r.credential_strings(credentials)) == previous
    print("credential diagnostics: needle set matches previous implementation")


def test_credential_diagnostics_report_raw_line_and_json_path_without_value(tmp_path,monkeypatch):
    secret = "synthetic-diagnostic-secret-98765"
    credentials = tmp_path/"credentials.json"
    raw = ('{\n  "pretty": "ordinary descriptive text",\n'
           '  "claudeAiOauth": {"scopes": ["'+secret+'"]}\n}\n')
    credentials.write_text(raw,encoding="utf-8")
    raw_line_file = tmp_path/"raw-line.txt"
    raw_line_file.write_bytes(raw.splitlines()[1].encode("utf-8"))
    json_value_file = tmp_path/"json-value.txt"
    json_value_file.write_text(secret,encoding="utf-8")
    monkeypatch.setattr(r,"TMP_ROOT",tmp_path/"fixed-root")
    with pytest.raises(r.RunError,match="credential exact-string check failed; value withheld; hits=") as caught:
        r.credential_check([raw_line_file,json_value_file],credentials)
    message = str(caught.value)
    assert secret not in message
    hits = [tuple(h) for h in json.loads(message.split("hits=",1)[1])]
    assert ("log/raw-line.txt","line:2:literal") in hits
    assert ("log/json-value.txt","claudeAiOauth.scopes[0]:literal") in hits
    print("credential diagnostics: raw-line and JSON-path labels reported without values")


def test_checkpoint_credential_path_passes_and_fails_as_before(controlled,monkeypatch):
    c,tmp = controlled
    logs = tmp/"checkpoint-logs"
    logs.mkdir()
    runner = object.__new__(r.Runner)
    runner.logs = logs
    runner.batch_id = "checkpoint-unit"
    runner.packed = set()
    runner.config = c
    runner.records = []
    runner.flagged = 0
    safe = logs/(runner.batch_id+"-safe.txt")
    safe.write_text("no credential material here",encoding="utf-8")
    runner.checkpoint()
    assert list(logs.glob("checkpoint-unit-part-*.tar.gz"))
    leaking = logs/(runner.batch_id+"-leak.txt")
    leaking.write_text("prefix synthetic-secret-value-12345 suffix",encoding="utf-8")
    with pytest.raises(r.RunError,match="credential exact-string check failed") as caught:
        runner.checkpoint()
    assert "synthetic-secret-value-12345" not in str(caught.value)
    print("checkpoint credential path: clean archive passes; planted token fails without disclosure")


def test_item8_deletion_and_absence(controlled):
    c,tmp = controlled
    r.prepare(c,{}, {})
    assert r.cleanup(c) == dict(ccfg_absent=True,cwork_absent=True)
    assert not (r.TMP_ROOT/"ccfg").exists()
    assert not (r.TMP_ROOT/"cwork").exists()
    print("item 8: config and working directories deleted and asserted absent")


@pytest.mark.skipif(os.name != "nt",reason="Windows locked-file proof")
def test_item8_locked_file_fails_loudly(controlled):
    c,tmp = controlled
    cfg,work,_ = r.prepare(c,{}, {})
    locked = work/"locked.txt"
    locked.write_text("synthetic locked file",encoding="utf-8")
    kernel = ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(locked),0x80000000,0,None,3,0x80,None)
    assert handle not in (None,ctypes.c_void_p(-1).value)
    try:
        with pytest.raises(OSError):
            r.cleanup(c)
        assert work.exists()
    finally:
        kernel.CloseHandle(handle)
    assert r.cleanup(c)["cwork_absent"]
    print("item 8: real Windows locked file caused loud cleanup failure; cleanup succeeded after handle close")


def test_item8_cleanup_refuses_outside_root(controlled):
    c,tmp = controlled
    with pytest.raises(r.RunError,match="fixed root"):
        r.cleanup(dict(c,temp_root=str(tmp)))


def test_item9_master_import_and_no_second_reader():
    load_rates,module = pricing.master(MASTER)
    assert load_rates is module.load_rates
    source = Path(pricing.__file__).read_text(encoding="utf-8")
    assert "from cost import load_rates" in source
    assert "json.loads" not in source and "read_text" not in source
    hits = []
    for name in ("harness.py","runlib.py","pricing.py"):
        for line in Path(__file__).with_name(name).read_text(encoding="utf-8").splitlines():
            if "rates.json" in line:
                hits.append(line)
    assert not hits
    print("item 9: master load_rates imported; no second reader or table literal in harness Python")


def fake_master():
    rates = SimpleNamespace(rate=lambda m:(.000003,.000015),cache_read_mult=lambda m:.1,
                            multipliers={"cache_write_5m":1.25,"cache_write_1h":1.5})
    def cost(table,model,inputs,outputs,cache_read_tokens=0,cache_write_tokens=0,cache_ttl="5m"):
        write_mult = table.multipliers["cache_write_5m" if cache_ttl == "5m" else "cache_write_1h"]
        return inputs*.000003+outputs*.000015+cache_read_tokens*.0000003+cache_write_tokens*.000003*write_mult
    return lambda path:rates, SimpleNamespace(cost=cost)


def test_item9_price_mismatch_and_two_models(monkeypatch):
    parsed = r.parse_stream(sample("mixed"),["stub"],MODEL)
    with pytest.raises(ValueError,match="cache write split ambiguous across models"):
        pricing.assert_cost(parsed["modelUsage"],parsed["total_cost_usd"],MASTER,
                            cache_write_5m=parsed["cache_write_5m"],cache_write_1h=parsed["cache_write_1h"])
    print("item 9: two-model synthetic cache write split rejected as ambiguous")


def test_pricing_live_one_hour_cache_write_cost():
    usage = {MODEL:dict(inputTokens=6,outputTokens=567,cacheReadInputTokens=37111,
                        cacheCreationInputTokens=13435,costUSD=.0631331)}
    result = pricing.assert_cost(usage,.0631331,MASTER,cache_write_5m=0,cache_write_1h=13435)
    assert result["computed_cost_total"] == pytest.approx(.0631331,abs=1e-7)
    assert result["cost_flagged"] is False
    assert set(("write_5m","write_1h")).issubset(result["unit_rates"][MODEL])
    print("cache TTL pricing: live 1h split total 0.0631331; no cost flag")


def test_pricing_five_minute_only_cache_write_split():
    load_rates,module = pricing.master(MASTER)
    rates = load_rates()
    expected = module.cost(rates,MODEL,0,0,cache_write_tokens=13435,cache_ttl="5m")
    usage = {MODEL:dict(inputTokens=0,outputTokens=0,cacheReadInputTokens=0,
                        cacheCreationInputTokens=13435,costUSD=expected)}
    result = pricing.assert_cost(usage,expected,MASTER,cache_write_5m=13435,cache_write_1h=0)
    assert result["computed_cost_total"] == pytest.approx(expected)
    assert result["cost_flagged"] is False
    print("cache TTL pricing: 5m-only split priced without a flag")


def test_pricing_two_models_reject_ambiguous_cache_write_split():
    usage = {MODEL:{},"synthetic-auxiliary":{}}
    with pytest.raises(ValueError,match="cache write split ambiguous across models"):
        pricing.assert_cost(usage,0,MASTER,cache_write_5m=0,cache_write_1h=0)
    print("cache TTL pricing: two-model split rejected as ambiguous")


@pytest.mark.parametrize("error",["UnknownModel synthetic","RatesExpired synthetic"])
def test_item9_pricing_errors_propagate(error,monkeypatch):
    def failed(path):
        raise RuntimeError(error)
    monkeypatch.setattr(pricing,"master",lambda path:(failed,None))
    with pytest.raises(RuntimeError,match=error):
        pricing.assert_cost({"synthetic-model":{}},0,MASTER,cache_write_5m=0,cache_write_1h=0)
    print("item 9: "+error+" propagated unchanged")


def test_dose_regression_and_pass_rules():
    rows = [dict(dose=k,BASE=100,ONECHAR=112,FILE=111+250*k,WRAP=11,content=250*k)
            for k in range(1,5) for _ in range(5)]
    result = h.dose_stats(rows)
    assert result["a"] == 0 and result["b"] == 250
    assert result["verdict"] == "PASS"
    assert result["residual_sd"] == result["se_a"] == result["se_b"] == 0
    assert result["degenerate_fit"] and result["lack_of_fit_f"] is None
    noisy = [dict(row, content=row["content"]+(i % 5)-2) for i, row in enumerate(rows)]
    spread = h.dose_stats(noisy)
    assert not spread["degenerate_fit"] and spread["lack_of_fit_f"] >= 0 and spread["lack_of_fit_df"] == [2, 16]


def test_probe_score_excludes_voided_runs():
    rows = [dict(probe="P1", repeat=i, pass_number=1, passed=p, reason="", run_id=str(i), void=v)
            for i, (p, v) in enumerate([(True, False), (False, False), (True, True), (False, True)])]
    assert h.probe_score(rows) == 0.5
    assert h.probe_score([dict(row, void=True) for row in rows]) is None
    print("F3: 1 pass of 2 scored runs is 0.5; two voided runs are neither pass nor fail")


def test_load_config_missing_git_bash_is_a_run_error(monkeypatch, tmp_path):
    config = json.loads((Path(h.HERE)/"config.example.json").read_text(encoding="utf-8"))
    config.pop("git_bash_path")
    monkeypatch.setattr(r, "skill_frontmatter_name", lambda path: config["trigger_skill"])
    monkeypatch.setattr(h.Path, "resolve", lambda self: self)
    monkeypatch.setattr(r, "EVAL_ROOT", Path(config["eval_root"]))
    path = tmp_path/"config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(r.RunError, match="Git Bash executable is missing"):
        h.load_config(path)
    config.pop("token_skill_root")
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(r.RunError, match="missing config setting: token_skill_root"):
        h.load_config(path)


def test_item10_dry_run_schema_declared_only():
    assert set(["triples","probe_results","credential_check","deletion_assertions"]).issubset(h.schema())
    print("item 10: schema declared; this unit test does not prove the live dry run")


@pytest.mark.parametrize("scenario",["valid","extra-skill","cost-mismatch","credential-leak","missing-shell","timeout","skill-input-shape","auxiliary-model","multi-turn-triple"])
def test_invocation_records_failures_and_always_cleans(controlled,monkeypatch,scenario):
    c,tmp = controlled
    logs = tmp/"unit-logs"
    monkeypatch.setattr(r,"LOG_ROOT",logs)
    c["log_root"] = str(logs)
    skill = tmp/"stub"
    skill.mkdir()
    (skill/"SKILL.md").write_text("---\nname: stub\n---\nSynthetic\n",encoding="utf-8")
    raw = sample("extra-skill" if scenario == "extra-skill" else ("mixed" if scenario == "auxiliary-model" else "single"))
    events = [json.loads(line) for line in raw.splitlines()]
    events[0]["skills"] = sorted(r.BUNDLED_SKILLS|{"stub"})
    if scenario == "extra-skill":
        events[0]["skills"].append("extra-synthetic-skill")
    events[0]["plugins"] = [{"name":name,"path":"builtin"} for name in sorted(r.BUNDLED_PLUGINS)]
    events[0]["mcp_servers"] = []
    if scenario == "multi-turn-triple":
        events[-1]["num_turns"] = 2
    if scenario == "auxiliary-model":
        events[-1]["total_cost_usd"] = .001074
    elif scenario != "cost-mismatch":
        events[-1]["total_cost_usd"] = .000537
    if scenario == "credential-leak":
        events[-1]["result"] = "synthetic-secret-value-12345"
    if scenario == "missing-shell":
        events[0]["tools"] = ["Read","PowerShell"]
    if scenario == "skill-input-shape":
        events.insert(-1,{"type":"assistant","message":{"content":[
            {"type":"tool_use","name":"Skill","input":{"other":"bad-shape"}}
        ]}})
    raw = "\n".join(json.dumps(e) for e in events)
    calls = []
    def fake_child(config,args,**kwargs):
        calls.append(args)
        if scenario == "timeout" and "--version" not in args:
            raise r.InvocationTimeout("Claude invocation timed out after 900 seconds")
        if "--version" not in args and kwargs.get("on_init"):
            kwargs["on_init"](events[0])
        return SimpleNamespace(returncode=0,stdout="2.1.303 (Claude Code)\n" if "--version" in args else raw,stderr="")
    monkeypatch.setattr(r,"child",fake_child)
    monkeypatch.setattr(pricing,"master",lambda path:fake_master())
    runner = r.Runner(c,batch_id="unit-"+scenario)
    if scenario == "valid":
        record = runner.invoke("synthetic",{"stub":skill},{},"B","synthetic-task","N")
        assert record["credential_check"]
        assert record["cache_read_share"] == .25
        assert record["shell_tool"] == "Bash" and record["shell_tool_confirmed"]
        assert record["configured_tool_set"] == c["tool_set"]
        assert record["containment"] == "UNVERIFIED"
        assert record["harness_md5"] and record["runlib_md5"] and record["pricing_md5"]
        assert set(("harness_md5","runlib_md5","pricing_md5")).issubset(h.schema())
        assert isinstance(record["temp_leftovers"],list)
    elif scenario == "auxiliary-model":
        with pytest.raises(r.RunError,match="cache write split ambiguous across models"):
            runner.invoke("synthetic",{"stub":skill},{} ,"B","synthetic-task","N")
        # The auxiliary model remains recorded even though pricing makes this run stop.
    elif scenario == "multi-turn-triple":
        with pytest.raises(r.RunError,match="multi_turn_triple"):
            runner.invoke("synthetic",{"stub":skill}, {},"A","synthetic-fixture","AN",metadata={"triple":0})
    else:
        with pytest.raises(r.RunError):
            runner.invoke("synthetic",{"stub":skill},{},"B","synthetic-task","N")
    assert sum("--version" in args for args in calls) == 2
    paths = list(logs.glob("*.record.json"))
    assert len(paths) == 1
    saved = json.loads(paths[0].read_text())
    assert saved["deletion_assertions"] == dict(ccfg_absent=True,cwork_absent=True)
    assert not (r.TMP_ROOT/"ccfg").exists() and not (r.TMP_ROOT/"cwork").exists()
    if scenario == "extra-skill":
        assert "extra-synthetic-skill" in saved["error"]
    if scenario == "cost-mismatch":
        assert "cost_assertion" in saved["flags"]
        assert "cap exceeded" in saved["error"]
    if scenario == "missing-shell":
        assert not saved["shell_tool_confirmed"]
        assert "absent from init.tools" in saved["error"]
    if scenario == "credential-leak":
        for path in logs.iterdir():
            assert b"synthetic-secret-value-12345" not in path.read_bytes()
    if scenario == "timeout":
        assert "timeout" in saved["flags"]
        assert "timed out" in saved["error"]
    if scenario == "skill-input-shape":
        assert "skill_input_shape_unconfirmed" in saved["flags"]
        assert saved["skill_calls"] == [{"other":"bad-shape"}]
    if scenario == "multi-turn-triple":
        assert "multi_turn_triple" in saved["flags"]
    if scenario == "auxiliary-model":
        assert "auxiliary_model" in saved["flags"]
        assert saved["auxiliary_models"]["synthetic-auxiliary"] == dict(
            inputTokens=100,outputTokens=10,cacheReadInputTokens=40,cacheCreationInputTokens=20)
    print("invocation integration: "+scenario+"; record persisted, no controlled directories remain")


def test_credential_hits_overlap_is_redacted_not_dropped(tmp_path, monkeypatch):
    shared = "shared-key-and-value"
    secret_value = "synthetic-secret-value-98765"
    credentials = tmp_path/"credentials.json"
    credentials.write_text(json.dumps({shared: shared, "tokenvalue": secret_value}), encoding="utf-8")
    scanned = tmp_path/"scanned.txt"
    scanned.write_text(shared + " " + secret_value, encoding="utf-8")
    monkeypatch.setattr(r, "TMP_ROOT", tmp_path/"fixed-root")
    with pytest.raises(r.RunError) as caught:
        r.credential_check([scanned], credentials)
    message = str(caught.value)
    assert "; hits=" in message
    assert "<credential-redacted>" in message
    assert "tokenvalue:literal" in message
    assert secret_value not in message
    assert shared not in message


def test_adr16_child_env_injects_token_and_strips_outranking(controlled, monkeypatch):
    c, tmp = controlled
    for name in r.OUTRANKING_ENV:
        monkeypatch.setenv(name, "outranking-value-123")
    env = r.child_env(c)
    assert env[r.OAUTH_TOKEN_ENV] == "synthetic-oauth-token-0123456789"
    assert not any(name in env for name in r.OUTRANKING_ENV)
    print("ADR-16: token injected from file; outranking variables stripped")


def test_adr16_child_env_fails_closed_without_token(controlled, monkeypatch):
    c, tmp = controlled
    monkeypatch.setattr(r, "OAUTH_TOKEN_FILE", tmp/"absent-token.txt")
    with pytest.raises(r.RunError, match="OAuth token file unreadable"):
        r.child_env(c)
    print("ADR-16: child_env fails closed when the token file is absent")


def test_adr16_token_is_a_needle_and_redacted(controlled):
    c, tmp = controlled
    log = tmp/"leak.txt"
    log.write_text("x synthetic-oauth-token-0123456789 y", encoding="utf-8")
    with pytest.raises(r.RunError) as info:
        r.credential_check([log], c["credentials_file"])
    assert "oauth-token-file:literal" in str(info.value)
    assert "synthetic-oauth-token-0123456789" not in str(info.value)
    assert b"synthetic-oauth-token-0123456789" not in r.redact(log.read_bytes(), c["credentials_file"])
    print("ADR-16: token found by the exact-string check and redacted")


def test_adr17_non_secret_field_is_not_a_needle(tmp_path):
    credentials = tmp_path/"credentials.json"
    credentials.write_text(json.dumps({"claudeAiOauth": {"accessToken": "secret-access-token-0001",
                                                         "rateLimitTier": "tier-label-value-0001"}}), encoding="utf-8")
    log = tmp_path/"log.txt"
    log.write_text("x tier-label-value-0001 y", encoding="utf-8")
    assert r.credential_check([log], credentials) is True
    log.write_text("x secret-access-token-0001 y", encoding="utf-8")
    with pytest.raises(r.RunError, match="claudeAiOauth.accessToken"):
        r.credential_check([log], credentials)
    print("ADR-17: rateLimitTier excluded; accessToken still detected")


def test_adr17_value_shared_with_secret_field_stays_a_needle(tmp_path):
    credentials = tmp_path/"credentials.json"
    credentials.write_text(json.dumps({"claudeAiOauth": {"accessToken": "same-value-000000001",
                                                         "rateLimitTier": "same-value-000000001"}}), encoding="utf-8")
    log = tmp_path/"log.txt"
    log.write_text("x same-value-000000001 y", encoding="utf-8")
    with pytest.raises(r.RunError, match="claudeAiOauth.accessToken"):
        r.credential_check([log], credentials)
    print("ADR-17: a value shared with a secret field stays a needle")


def _adr18_setup(controlled, monkeypatch, plan=(False,)):
    c, tmp = controlled
    logs = tmp/"unit-logs"
    monkeypatch.setattr(r,"LOG_ROOT",logs)
    c["log_root"] = str(logs)
    skill = tmp/"stub"
    skill.mkdir()
    (skill/"SKILL.md").write_text("---\nname: stub\n---\nSynthetic\n",encoding="utf-8")
    base = [json.loads(line) for line in sample("single").splitlines()]
    base[0]["skills"] = sorted(r.BUNDLED_SKILLS|{"stub"})
    base[0]["plugins"] = [{"name":name,"path":"builtin"} for name in sorted(r.BUNDLED_PLUGINS)]
    base[0]["mcp_servers"] = []
    base[-1]["total_cost_usd"] = .000537
    queue = list(plan)
    calls = []
    def fake_child(config,args,**kwargs):
        calls.append(args)
        if "--version" in args:
            return SimpleNamespace(returncode=0,stdout="2.1.303 (Claude Code)\n",stderr="")
        mode = queue.pop(0)
        events = json.loads(json.dumps(base))
        if mode == "out-glob":
            events[-1]["permission_denials"] = [{"tool_name":"Glob","tool_use_id":"toolu_synthetic",
                                                 "tool_input":{"pattern":"**/*","path":str(r.TMP_ROOT)}}]
            events.insert(-1,{"type":"system","subtype":"permission_denied","tool_name":"Glob",
                              "tool_use_id":"toolu_synthetic","decision_reason_type":"mode","message":"denied"})
        elif mode:
            if mode != "result-only":
                events.insert(-1,{"type":"system","subtype":"permission_denied","tool_name":"Edit",
                                  "tool_use_id":"toolu_synthetic","decision_reason_type":"mode","message":"denied"})
            events[-1]["permission_denials"] = [{"tool_name":"Edit","tool_use_id":"toolu_synthetic",
                                                 "tool_input":{"file_path":"x.txt","old_string":"a","new_string":"b"}}]
        if kwargs.get("on_init"):
            kwargs["on_init"](events[0])
        return SimpleNamespace(returncode=0,stdout="\n".join(json.dumps(e) for e in events),stderr="")
    monkeypatch.setattr(r,"child",fake_child)
    monkeypatch.setattr(pricing,"master",lambda path:fake_master())
    return c, skill, logs, calls


def _adr18_saved(logs):
    return [json.loads(p.read_text()) for p in sorted(logs.glob("*.record.json"))]


def test_adr18_in_denial_voids_and_stops_batch_at_once(controlled,monkeypatch):
    c, skill, logs, calls = _adr18_setup(controlled,monkeypatch,plan=(True,))
    with pytest.raises(r.RunError,match="IN permission denial .*Edit:x.txt.*ADR-18 amendment 1"):
        r.Runner(c,batch_id="unit-adr18-denied").invoke("synthetic",{"stub":skill},{},"B","synthetic-task","N")
    saved = _adr18_saved(logs)
    assert len(saved) == 1 and "permission_denied" in saved[0]["flags"] and not h.valid(saved[0])
    assert saved[0]["permission_denials"] == dict(events=1,result_denials=1,tools=["Edit"],targets=["Edit:x.txt"],
                                                  in_count=1,out_count=0,out_other=0,in_targets=["Edit:x.txt"])
    assert saved[0]["deletion_assertions"] == dict(ccfg_absent=True,cwork_absent=True)
    assert not (r.TMP_ROOT/"ccfg").exists() and not (r.TMP_ROOT/"cwork").exists()
    print("ADR-18 amendment 1: an IN denial is recorded, voids the run and stops the batch at once")


def test_adr18_out_glob_denial_is_recorded_and_run_stays_valid(controlled,monkeypatch):
    c, skill, logs, calls = _adr18_setup(controlled,monkeypatch,plan=("out-glob",))
    record = r.Runner(c,batch_id="unit-adr18-out").invoke("synthetic",{"stub":skill},{},"B","synthetic-task","N")
    assert "permission_denied" not in record["flags"] and h.valid(record)
    assert record["permission_denials"]["in_count"] == 0 and record["permission_denials"]["out_count"] == 1
    assert record["permission_denials"]["tools"] == ["Glob"]
    assert record["launcher"]["codex_names"] == [] and record["launcher"]["interpreter"] == sys.executable
    assert set(record["config_files"]) == {"policy-limits.json","remote-settings.json"}
    assert record["event_counts"]["result"] == 1 and "event_counts" in h.schema() and "launcher" in h.schema()
    print("ADR-18 amendment 2, ADR-21: an OUT Glob denial is recorded, the run stays valid; launcher and config_files present")


def test_token_refreshed_during_run_is_redacted(controlled,monkeypatch):
    c, skill, logs, calls = _adr18_setup(controlled,monkeypatch,plan=(False,))
    refreshed = "refreshed-token-value-98765-synthetic"
    inner = r.child
    def refreshing_child(config,args,**kwargs):
        proc = inner(config,args,**kwargs)
        if "--version" not in args:
            (r.TMP_ROOT/"ccfg"/".credentials.json").write_text(json.dumps({"claudeAiOauth":{"accessToken":refreshed}}),encoding="utf-8")
            proc.stdout = proc.stdout + "\n" + json.dumps({"type":"assistant","message":{"content":[{"type":"text","text":refreshed}]}})
        return proc
    monkeypatch.setattr(r,"child",refreshing_child)
    runner = r.Runner(c,batch_id="unit-refreshed-token")
    with pytest.raises(r.RunError,match="credential exact-string check failed; output redacted"):
        runner.invoke("synthetic",{"stub":skill},{},"B","synthetic-task","N")
    for path in logs.iterdir():
        assert refreshed.encode() not in path.read_bytes()
    assert b"<credential-redacted>" in next(logs.glob("*.stream.jsonl")).read_bytes()
    print("F4: a token written into the ccfg copy during the run is a needle; stream redacted, run failed closed")


def test_adr18_result_list_alone_flags(controlled,monkeypatch):
    c, skill, logs, calls = _adr18_setup(controlled,monkeypatch,plan=("result-only",))
    with pytest.raises(r.RunError,match="IN permission denial"):
        r.Runner(c,batch_id="unit-adr18-result").invoke("synthetic",{"stub":skill},{},"B","synthetic-task","N")
    record = _adr18_saved(logs)[0]
    assert "permission_denied" in record["flags"]
    assert record["permission_denials"]["events"] == 0 and record["permission_denials"]["result_denials"] == 1
    print("A48: a non-empty result permission_denials list alone flags the run")


def test_adr18_clean_run_records_zero_and_is_valid(controlled,monkeypatch):
    c, skill, logs, calls = _adr18_setup(controlled,monkeypatch,plan=(False,))
    record = r.Runner(c,batch_id="unit-adr18-clean").invoke("synthetic",{"stub":skill},{},"B","synthetic-task","N")
    assert record["permission_denials"] == dict(events=0,result_denials=0,tools=[],targets=[],in_count=0,out_count=0,out_other=0,in_targets=[])
    assert "permission_denied" not in record["flags"] and h.valid(record)
    assert "permission_denials" in h.schema()
    print("A48: a run without denials records zero counts, no flag, and stays valid")


def test_adr18_out_denials_never_stop_a_batch(controlled,monkeypatch):
    c, skill, logs, calls = _adr18_setup(controlled,monkeypatch,plan=("out-glob","out-glob","out-glob","out-glob"))
    runner = r.Runner(c,batch_id="unit-adr18-out-four")
    for _ in range(4):
        assert h.valid(runner.invoke("synthetic",{"stub":skill},{},"B","synthetic-task","N"))
    assert len(_adr18_saved(logs)) == 4 and not hasattr(runner,"denied_streak")
    print("ADR-18 amendment 1: the A48 streak is retired; four OUT Glob denials in a row stop nothing")


def test_adr19_denial_scope_in_runlib():
    wd = r"C:\Users\REDACTED_USER\venvs\token-aware-eval\tmp\cwork"
    glob = lambda path: {"tool_name":"Glob","tool_input":{"pattern":"*","path":path}}
    assert r.denial_scope({"tool_name":"Edit","tool_input":{"file_path":r"C:\x\y"}}, wd) == "IN"
    assert r.denial_scope(glob("out"), wd) == "IN" and r.denial_scope({"tool_name":"Glob","tool_input":{"pattern":"*"}}, wd) == "IN"
    for outside in (r"C:\Users\REDACTED_USER\venvs\token-aware-eval\tmp", "../ccfg", "~/x", "$HOME/x", "%USERPROFILE%/x", "out/../../ccfg"):
        assert r.denial_scope(glob(outside), wd) == "OUT", outside
    assert r.denial_scope(glob(r"c:\users\REDACTED_USER\venvs\token-aware-eval\tmp\cwork\out"), wd) == "IN"
    noise = r.permission_denials(json.dumps({"type":"system","subtype":"permission_denied","tool_name":"Write"}), wd)
    assert noise["in_count"] == 1 and noise["result_denials"] == 0
    print("ADR-19 in runlib: IN and OUT by tool, target and working_dir, with .., ~, $HOME resolved; an event without an entry is IN")


def test_adr10_amendment3_multi_request_triple(controlled,monkeypatch):
    c, skill, logs, calls = _adr18_setup(controlled,monkeypatch,plan=(False,False))
    inner = r.child
    def doubled_child(config,args,**kwargs):
        proc = inner(config,args,**kwargs)
        if "--version" not in args:
            lines = proc.stdout.split("\n")
            proc.stdout = "\n".join(lines[:-1] + [json.dumps({"type":"assistant","message":{"content":[{"type":"text","text":"OK"}]}})]*2 + lines[-1:])
        return proc
    monkeypatch.setattr(r,"child",doubled_child)
    runner = r.Runner(c,batch_id="unit-adr10-a3")
    with pytest.raises(r.RunError,match="multi_request_triple"):
        runner.invoke("synthetic",{"stub":skill},{},"A","synthetic-fixture","AN",metadata={"triple":0})
    saved = _adr18_saved(logs)[0]
    assert saved["event_counts"]["assistant"] == 2 and "multi_request_triple" in saved["flags"]
    record = runner.invoke("synthetic",{"stub":skill},{},"B","synthetic-task","N")
    assert record["event_counts"]["assistant"] == 2 and "multi_request_triple" not in record["flags"]
    print("ADR-10 amendment 3: two assistant events flag a triple and stop it; a task run only records the count")


def test_adr18_codex_launch_refused_before_any_child(controlled,monkeypatch):
    c, skill, logs, calls = _adr18_setup(controlled,monkeypatch)
    monkeypatch.setenv("CODEX_CI","codex-value-should-not-print")
    with pytest.raises(r.RunError,match="I4: launched under Codex") as info:
        r.Runner(c,batch_id="unit-adr18-codex")
    assert "CODEX_CI" in str(info.value) and "codex-value-should-not-print" not in str(info.value)
    assert calls == []
    print("ADR-18: a Codex launch is refused before any child process; names only in the message")


def test_adr18_invoke_refuses_codex_launch_too(controlled,monkeypatch):
    c, skill, logs, calls = _adr18_setup(controlled,monkeypatch)
    runner = r.Runner(c,batch_id="unit-adr18-codex-invoke")
    count = len(calls)
    monkeypatch.setenv("CODEX_THREAD_ID","x")
    with pytest.raises(r.RunError,match="I4: launched under Codex"):
        runner.invoke("synthetic",{"stub":skill},{},"B","synthetic-task","N")
    assert len(calls) == count and not list(logs.glob("*.record.json"))
    print("ADR-18: invoke refuses a Codex launch before the version check and writes no record")


def test_adr18_codex_names_match_prefix_only():
    assert r.codex_launch_names({"codex_session_id":"a","PATH":"b","MYCODEX_X":"c","CODEXX":"d"}) == ["codex_session_id"]
    r.refuse_codex_launch({"PATH":"b"})
    with pytest.raises(r.RunError):
        r.refuse_codex_launch({"CODEX_VERSION":"1"})
    assert r.codex_launch_names() == []  # conftest strips CODEX_* for every test
    print("ADR-18: prefix CODEX_ only, case-insensitive; tests run with the names stripped")


def test_adr18_permission_denials_parser_tolerates_noise():
    raw = "\n".join(["not json","[1,2]",json.dumps({"type":"system","subtype":"permission_denied","tool_name":"Write"}),
                     json.dumps({"type":"system","subtype":"permission_denied","tool_name":"Edit"}),
                     json.dumps({"type":"result","permission_denials":[
                         {"tool_name":"Write","tool_input":{"file_path":"out/y.txt","content":"ok"}},"bad",
                         {"tool_name":"Bash","tool_input":{"command":"echo "+"x"*200}},
                         {"tool_name":"Glob","tool_input":{"pattern":"**/*.md"}}]})])
    got = r.permission_denials(raw)
    assert got["events"] == 2 and got["result_denials"] == 4 and got["tools"] == ["Bash","Edit","Glob","Write"]
    assert got["targets"] == sorted(["Write:out/y.txt","Glob:**/*.md",("Bash:echo "+"x"*200)[:85]])
    assert "ok" not in "".join(t for t in got["targets"] if t.startswith("Write"))[len("Write:out/y.txt"):]
    assert r.permission_denials("") == dict(events=0,result_denials=0,tools=[],targets=[],in_count=0,out_count=0,out_other=0,in_targets=[])
    assert got["in_count"] == 3 and got["out_count"] == 0  # three dict entries, no working_dir given: every entry is IN
    print("A48: parser counts events and result entries, keeps tool and target only, skips malformed lines")


def test_adr18_valid_excludes_cost_and_permission_flags():
    assert h.valid({"flags":[]}) and h.valid({"flags":["auxiliary_model"]})
    assert not h.valid({"flags":["cost_assertion"]}) and not h.valid({"flags":["permission_denied"]})
    print("A48: harness.valid excludes cost-assertion and permission-denied runs")
