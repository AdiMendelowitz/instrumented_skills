"""Build synthetic fixtures and append the command-14 artifact manifest."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
print("Configured Git Bash executable: "+str(git_bash)+"; is_file="+str(git_bash.is_file()))
if not git_bash.is_file():
    raise RuntimeError("configured Git Bash executable is missing")
SAMPLES = HERE/"samples"
SAMPLES.mkdir(exist_ok=True)
model = "claude-sonnet-5-5"
init = dict(type="system",subtype="init",model=model,skills=["stub"],tools=["Read","Edit","Write","Bash","Skill","Glob","Grep"])
usage = dict(input_tokens=100,output_tokens=10,cache_creation_input_tokens=20,cache_read_input_tokens=40)
model_usage = dict(inputTokens=100,outputTokens=10,cacheCreationInputTokens=20,cacheReadInputTokens=40,costUSD=.001)
result = dict(type="result",subtype="success",is_error=False,result="OK",usage=usage,
              total_cost_usd=.001,modelUsage={model:model_usage},num_turns=1,duration_ms=100)
tool = dict(type="assistant",message=dict(content=[dict(type="tool_use",id="synthetic-tool",name="Skill",input=dict(skill="token-aware"))]))
def write(name,events):
    (SAMPLES/name).write_text("".join(json.dumps(e,sort_keys=True)+"\n" for e in events),encoding="utf-8",newline="\n")
write("single.synthetic.jsonl",[init,result])
write("trigger.synthetic.jsonl",[init,tool,result])
extra = dict(init,skills=["stub","extra-synthetic-skill"])
write("extra-skill.synthetic.jsonl",[extra,result])
mix = json.loads(json.dumps(result))
mix["modelUsage"]["synthetic-auxiliary"] = dict(model_usage)
mix["total_cost_usd"] = .002
write("mixed.synthetic.jsonl",[init,mix])
prereg = dict(claude_version="synthetic",model_id="synthetic",harness_md5="0"*32,
              bootstrap_seed=71,within_seed=19,exclusion_cap=0,preregistered_r=5,
              probe_thresholds={"F2":[1.0,.9,.95,.97,.99]},unedited_content_tokens={"F2":1000},
              pool_size=10000,task_count=6,fixture_count=1,probe_count=15)
records = []
for task in range(6):
    for arm in ("N","K0","K1"):
        for rep in range(5):
            cost = (1+.1*task+.02*rep)*({"N":.9,"K0":1,"K1":.7}[arm])
            usage = dict(inputTokens=100,outputTokens=10,cacheCreationInputTokens=20,cacheReadInputTokens=40,costUSD=cost)
            rec = dict(run_id=f"T{task}/{arm}/{rep}",track="B",task_or_fixture_id=f"T{task}",arm=arm,
                       batch_id="synthetic",claude_version="synthetic",model_id="synthetic",harness_md5="0"*32,
                       flags=[],computed_cost_total=cost,computed_cost_per_model={"synthetic":cost},
                       check_exit_code=0,triggered=arm == "K1",modelUsage={"synthetic":usage},
                       unit_rates={"synthetic":dict(input=.001,output=.002,read=.0001,write=.00125)},
                       usage=dict(input_tokens=100,output_tokens=10,cache_creation_input_tokens=20,cache_read_input_tokens=40))
            records.append(rec)
for arm in ("AN","AS","ASn"):
    for rep in range(5):
        size = (1000+rep*10)*(1 if arm == "AN" else .8)
        rec = dict(run_id=f"F2/{arm}/{rep}",track="A",task_or_fixture_id="F2",arm=arm,
                   batch_id="synthetic",claude_version="synthetic",model_id="synthetic",harness_md5="0"*32,flags=[],
                   triggered=arm == "ASn",first_pass_score=1.0,second_pass_score=None,
                   triples=[dict(BASE=100,ONECHAR=111,FILE=110+size,WRAP=10,content=size) for _ in range(5)])
        records.append(rec)
for filename,obj in (("pilot.json",records),("prereg.json",prereg)):
    (HERE/"analysis-fixtures"/filename).write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")
files = ["harness.py","runlib.py","pricing.py","test_harness.py","analysis.py","test_analysis.py","config.example.json","samples/dose-block.txt"]
lines = ["\n## Command 14 artifact MD5 manifest\n"]
for name in files:
    digest = hashlib.md5((HERE/name).read_bytes()).hexdigest()
    line = name+": "+digest
    print(line)
    lines.append(line+"\n")
recipe = HERE/"environment-recipe.md"
text = recipe.read_text(encoding="utf-8").split("\n## Command 14 artifact MD5 manifest\n",1)[0]
recipe.write_text(text+"\n"+"".join(lines),encoding="utf-8",newline="\n")
print("COMMAND 14: artifact files written; synthetic event samples labelled; live verification pending")
