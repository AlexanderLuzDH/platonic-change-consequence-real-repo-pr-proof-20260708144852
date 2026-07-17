#!/usr/bin/env python3
"""Static, history-grounded evidence-state audit of the BugsInPy corpus."""
from __future__ import annotations
import argparse, csv, json, math, random, re, shlex
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

TEST_DIRS={"test","tests","testing","spec","specs"}
STOP={"src","source","lib","test","tests","testing","spec","core","main","utils","util","base","module","modules","python"}

def norm(s:str)->str:
    s=s.strip().strip("'\"").replace("\\","/")
    while s.startswith("./"): s=s[2:]
    return PurePosixPath(s).as_posix()

def is_test(s:str)->bool:
    p=PurePosixPath(norm(s)); parts=[x.lower() for x in p.parts]; n=p.name.lower()
    return any(x in TEST_DIRS for x in parts[:-1]) or n.startswith("test_") or n.endswith("_test.py")

def is_source(s:str)->bool:
    return PurePosixPath(norm(s)).suffix.lower() in {".py",".pyx"} and not is_test(s)

def shell_info(p:Path)->dict[str,str]:
    out={}
    for raw in p.read_text(encoding="utf-8",errors="replace").splitlines():
        line=raw.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k,v=line.split("=",1)
        try: x=shlex.split(v); out[k.strip()]=" ".join(x) if x else ""
        except ValueError: out[k.strip()]=v.strip("'\"")
    return out

def test_paths(text:str)->set[str]:
    return {norm(x.split("::",1)[0]) for x in re.findall(r"[A-Za-z0-9_./-]+\.(?:py|pyx)(?:::)?",text)}

@dataclass
class FilePatch:
    path:str; added:list[str]; removed:list[str]

def patch_files(text:str)->list[FilePatch]:
    out=[]; cur=None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            m=re.match(r"diff --git a/(.*?) b/(.*)$",line)
            cur=FilePatch(norm(m.group(2)),[],[]) if m else None
            if cur: out.append(cur)
        elif cur and not line.startswith(("+++ ","--- ","@@")):
            if line.startswith("+"): cur.added.append(line[1:])
            elif line.startswith("-"): cur.removed.append(line[1:])
    return out

def candidates(src:str)->set[str]:
    p=PurePosixPath(norm(src)); stem=p.stem
    out={f"tests/test_{stem}.py",f"test/test_{stem}.py",str(p.with_name(f"test_{stem}.py")),f"tests/{stem}_test.py"}
    if p.parts and p.parts[0].lower() in {"src","lib","source"}:
        q=PurePosixPath(*p.parts[1:]); out|={str(PurePosixPath("tests")/q.with_name(f"test_{q.stem}.py")),str(PurePosixPath("tests")/q)}
    return {norm(x) for x in out}

def toks(text:str)->set[str]:
    return {x for x in re.findall(r"[a-z0-9]+",text.lower()) if len(x)>1 and x not in STOP}

@dataclass
class Record:
    project:str; bug_id:str; python_version:str; buggy_commit_id:str; fixed_commit_id:str
    benchmark_tests:list[str]; changed_sources:list[str]; changed_tests:list[str]
    relevant_test_changed:bool; benchmark_test_preexisting_proxy:bool; any_test_changed:bool; unrelated_test_change_only:bool
    same_stem_discoverable:bool; candidate_path_discoverable:bool; lexical_behavior_overlap:bool

def record(project:Path,bug:Path)->Record|None:
    ip,pp=bug/"bug.info",bug/"bug_patch.txt"
    if not ip.is_file() or not pp.is_file(): return None
    info=shell_info(ip); fps=patch_files(pp.read_text(encoding="utf-8",errors="replace"))
    src=sorted({f.path for f in fps if is_source(f.path)}); changed_tests=sorted({f.path for f in fps if is_test(f.path)})
    relevant=test_paths(info.get("test_file",""))
    rp=bug/"run_test.sh"
    if rp.is_file(): relevant|=test_paths(rp.read_text(encoding="utf-8",errors="replace"))
    if not src or not relevant: return None
    changed=bool(relevant & set(changed_tests)); any_changed=bool(changed_tests)
    same=any(PurePosixPath(s).stem.lower() in PurePosixPath(t).stem.lower().replace("test_","").replace("_test","") for s in src for t in relevant)
    exact=any(t in candidates(s) for s in src for t in relevant)
    source_words=set(); test_words=set()
    for f in fps:
        if is_source(f.path): source_words|=toks(" ".join(f.added+f.removed))
        if is_test(f.path):
            names=re.findall(r"\b(?:def\s+(test_[A-Za-z0-9_]+)|class\s+(Test[A-Za-z0-9_]+))", "\n".join(f.added))
            test_words|=toks(" ".join(a or b for a,b in names))
    return Record(project.name,bug.name,info.get("python_version",""),info.get("buggy_commit_id",""),info.get("fixed_commit_id",""),sorted(relevant),src,changed_tests,changed,not changed,any_changed,any_changed and not changed,same,exact,bool(source_words&test_words))

def wilson(k:int,n:int,z:float=1.6448536269514722)->list[float]|None:
    if not n:return None
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-h),min(1,c+h)]

def cluster90(rs:list[Record],field:str,seed:int=61065,reps:int=5000)->list[float]|None:
    projects=sorted({r.project for r in rs})
    if not projects:return None
    groups={p:[r for r in rs if r.project==p] for p in projects}; rng=random.Random(seed); vals=[]
    for _ in range(reps):
        sample=[r for _p in (rng.choice(projects) for _ in projects) for r in groups[_p]]
        vals.append(sum(bool(getattr(r,field)) for r in sample)/len(sample))
    vals.sort(); return [vals[int(.05*(reps-1))],vals[int(.95*(reps-1))]]

def rate(rs:list[Record],field:str)->dict:
    k=sum(bool(getattr(r,field)) for r in rs); n=len(rs)
    return {"successes":k,"total":n,"rate":k/n if n else None,"wilson90":wilson(k,n),"project_cluster_bootstrap90":cluster90(rs,field)}

def summarize(rs:list[Record])->dict:
    ev={x:rate(rs,x) for x in ["relevant_test_changed","benchmark_test_preexisting_proxy","any_test_changed","unrelated_test_change_only"]}
    mp={x:rate(rs,x) for x in ["same_stem_discoverable","candidate_path_discoverable","lexical_behavior_overlap"]}
    n=len(rs); pre=ev["benchmark_test_preexisting_proxy"]["successes"]; mismatch=sum(r.benchmark_test_preexisting_proxy or r.unrelated_test_change_only for r in rs)
    no_any=[r for r in rs if not r.any_test_changed]
    return {
      "schema_version":1,"kind":"autonomous_assurance_bugsinpy_static_result",
      "claim_boundary":"Static metadata/patch proxies; not full bug reproduction and not a human-usefulness claim.",
      "dataset":{"eligible_records":n,"projects":len({r.project for r in rs}),"project_counts":dict(sorted(Counter(r.project for r in rs).items()))},
      "evidence_states":ev,"mapping":mp,
      "policy_tournament":{
        "obligation_first":{"emissions":n,"changed_test_proxy_precision":ev["relevant_test_changed"]["rate"],"preexisting_test_proxy_false_obligations":pre},
        "suppress_if_any_test_changed":{"emissions":len(no_any),"changed_test_proxy_precision":sum(r.relevant_test_changed for r in no_any)/len(no_any) if no_any else None,"preexisting_test_proxy_false_obligations":sum(r.benchmark_test_preexisting_proxy for r in no_any),"unrelated_test_change_suppressions":sum(r.unrelated_test_change_only for r in rs)},
        "benchmark_evidence_state_oracle":{"missing_test_obligations":0,"note":"Non-deployable upper bound using benchmark-selected test paths."}},
      "hypotheses":{
        "H1_preexisting_at_least_25pct":{"observed":pre/n if n else None,"passed":bool(n) and pre/n>=.25},
        "H2_binary_any_test_mismatch_at_least_10pct":{"observed":mismatch/n if n else None,"passed":bool(n) and mismatch/n>=.10},
        "H3_exact_filename_mapping_below_70pct":{"observed":mp["candidate_path_discoverable"]["rate"],"passed":bool(n) and mp["candidate_path_discoverable"]["rate"]<.70}}}

def markdown(s:dict)->str:
    pct=lambda x:"n/a" if x is None else f"{100*x:.1f}%"
    lines=["# Autonomous Assurance Lab v1 — BugsInPy static result","",s["claim_boundary"],"",f"Eligible cases: **{s['dataset']['eligible_records']}** across **{s['dataset']['projects']}** projects.","","| Measure | Count | Rate |","|---|---:|---:|"]
    for group in (s["evidence_states"],s["mapping"]):
        for name,row in group.items(): lines.append(f"| {name} | {row['successes']}/{row['total']} | {pct(row['rate'])} |")
    lines += ["","## Preregistered hypotheses"]
    for n,r in s["hypotheses"].items(): lines.append(f"- **{n}:** {'PASS' if r['passed'] else 'FAIL'} — {pct(r['observed'])}")
    return "\n".join(lines)+"\n"

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--json-output",type=Path,required=True); ap.add_argument("--markdown-output",type=Path,required=True); ap.add_argument("--csv-output",type=Path,required=True); a=ap.parse_args()
    rs=[]
    for p in sorted((a.root/"projects").iterdir()):
        if not (p/"bugs").is_dir(): continue
        for b in sorted((p/"bugs").iterdir()):
            if b.is_dir():
                x=record(p,b)
                if x: rs.append(x)
    s=summarize(rs); payload={"summary":s,"records":[asdict(x) for x in rs]}
    for path in [a.json_output,a.markdown_output,a.csv_output]: path.parent.mkdir(parents=True,exist_ok=True)
    a.json_output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8"); a.markdown_output.write_text(markdown(s),encoding="utf-8")
    with a.csv_output.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(asdict(rs[0])) if rs else []); w.writeheader()
        for x in rs:
            row=asdict(x)
            for k,v in row.items():
                if isinstance(v,list): row[k]=json.dumps(v)
            w.writerow(row)
    print(json.dumps(s,sort_keys=True)); return 0 if rs else 2
if __name__=="__main__": raise SystemExit(main())
