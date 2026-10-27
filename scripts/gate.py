#!/usr/bin/env python3
"""vertical-research gate: 산출물 형식 검사, Knock-Out·채점·순위 계산, 실행 간 업체 명부.

Usage:
  gate.py new-run       <output_dir> --vertical <버티컬> [--regions 북미,남미] [--config <config.md>]   (실행 폴더 생성, 경로 출력)
  gate.py check-records <run_dir> --config <config.md>
  gate.py score         <run_dir> --config <config.md>   (명부도 함께 갱신)
  gate.py registry      <output_dir> --config <config.md>
  gate.py check-report  <run_dir> --config <config.md>
  gate.py check-ko      <run_dir>

Exit code 0 = pass, 1 = gate fail, 2 = usage/config error. 표준 라이브러리만 쓴다.
"""
import argparse
import csv
import datetime
import glob
import json
import os
import re
import sys
from urllib.parse import urlparse

LEVELS = ("상", "중", "하")
UNKNOWN = "확인불가"
SEVERITIES = ("S1", "S2", "S3")
SCOPES = ("company", "vertical")
REGISTRY = "_registry"


def die(msg, code=2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def load_config(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        die(f"설정 파일을 읽을 수 없음: {e}")
    m = re.search(r"```json\s+vr-config\s*\n(.*?)\n```", text, re.S)
    if not m:
        die("설정 파일에 ```json vr-config 블록이 없음")
    try:
        cfg = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        die(f"vr-config JSON 파싱 실패: {e}")
    for key in ("top_n", "knockout", "scoring"):
        if key not in cfg:
            die(f"vr-config 에 '{key}' 가 없음")
    for item in cfg["scoring"]:
        for lv in LEVELS:
            if lv not in item.get("levels", {}):
                die(f"scoring {item.get('id')} 에 '{lv}' 점수가 없음")
        item.setdefault("scope", "vertical")
        if item["scope"] not in SCOPES:
            die(f"scoring {item.get('id')} 의 scope 는 company/vertical 중 하나여야 함")
    groups = cfg.setdefault("region_groups", {})
    if not isinstance(groups, dict) or not all(isinstance(v, list) and v for v in groups.values()):
        die("region_groups 는 {지역 이름: [국가 코드, ...]} 형식이어야 함")
    return cfg


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return e


def is_url(s):
    return isinstance(s, str) and re.match(r"https?://\S+", s) is not None


def name_key(name):
    # 괄호 속 영문명·옛 이름·사업부는 빼고 본래 이름으로 비교한다 ("휴먼인텍 (Humanintec)" = "휴먼인텍")
    name = (name or "").lower()
    base = re.sub(r"[^0-9a-z가-힣]", "", re.sub(r"\([^)]*\)", "", name))
    return base or re.sub(r"[^0-9a-z가-힣]", "", name)


def company_key(c):
    host = urlparse(c.get("homepage") or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host:
        return host
    return name_key(c.get("company"))


def run_folder_name(vertical, date):
    """버티컬 표기(한국어 그대로) + 날짜. 폴더명에 못 쓰는 문자와 공백은 '-' 로 바꾼다."""
    name = re.sub(r'[\\/:*?"<>|\s]+', "-", vertical.strip())
    name = re.sub(r"-{2,}", "-", name).strip("-.") or "vertical"
    return f"{name}-{date}"


def run_created(run_dir):
    """실행 순서 기준. run.json 의 created(new-run 이 기록), 없으면 run.json 수정 시각.
    채점을 다시 해도 바뀌지 않아야 하므로 scored.json 시각은 쓰지 않는다."""
    meta = load_json(os.path.join(run_dir, "run.json"))
    if isinstance(meta, dict) and meta.get("created"):
        try:
            return datetime.datetime.fromisoformat(meta["created"]).timestamp()
        except ValueError:
            pass
    path = os.path.join(run_dir, "run.json")
    return os.path.getmtime(path) if os.path.exists(path) else 0.0


def run_config(run_dir, cfg):
    """실행 폴더에 top_n 등을 덮어쓴 설정이 있으면 그것을 쓴다."""
    path = os.path.join(run_dir, "config.override.md")
    return load_config(path) if os.path.exists(path) else cfg


def run_countries(run_dir):
    """run.json 에 대륙 지역을 풀어 둔 국가 코드가 있으면 그 집합, 없으면 None (국가 제한 없음)."""
    meta = load_json(os.path.join(run_dir, "run.json"))
    if isinstance(meta, dict) and meta.get("countries"):
        return {c.upper() for c in meta["countries"]}
    return None


def run_vertical(run_dir):
    meta = load_json(os.path.join(run_dir, "run.json"))
    if isinstance(meta, dict) and meta.get("vertical"):
        return meta["vertical"]
    return os.path.basename(os.path.normpath(run_dir))


# ---------------------------------------------------------------- records

def validate_records(run_dir, cfg):
    """Return (errors, records_by_unit)."""
    errors, units = [], {}
    ko_ids = [k["id"] for k in cfg["knockout"]]
    scope = {s["id"]: s["scope"] for s in cfg["scoring"]}
    files = sorted(glob.glob(os.path.join(run_dir, "records", "*.json")))
    if not files:
        return ["records/*.json 이 하나도 없음"], units
    for path in files:
        name = os.path.basename(path)
        data = load_json(path)
        if isinstance(data, Exception):
            errors.append(f"{name}: JSON 읽기 실패 ({data})")
            continue
        comps = data.get("companies")
        if not isinstance(comps, list):
            errors.append(f"{name}: 'companies' 배열이 없음")
            continue
        unit = data.get("unit") or os.path.splitext(name)[0]
        units[unit] = comps
        for i, c in enumerate(comps):
            who = f"{name}#{i} {c.get('company', '?')}"
            if not c.get("company"):
                errors.append(f"{who}: company 비어 있음")
            seg = c.get("segment")
            if seg not in ("target", "competitor"):
                errors.append(f"{who}: segment 는 target/competitor 중 하나여야 함 (현재 {seg!r})")
                continue
            if c.get("homepage") and not is_url(c["homepage"]):
                errors.append(f"{who}: homepage 가 URL 이 아님")
            if seg == "competitor":
                continue
            ko = c.get("knockout") or {}
            for kid in ko_ids:
                k = ko.get(kid)
                if not isinstance(k, dict) or not isinstance(k.get("hit"), bool):
                    errors.append(f"{who}: knockout {kid} 누락 또는 hit 가 bool 아님")
                elif k["hit"] and not is_url(k.get("source")):
                    errors.append(f"{who}: knockout {kid} hit=true 인데 source URL 없음")
            sc = c.get("scores") or {}
            for sid, sc_scope in scope.items():
                s = sc.get(sid)
                if not isinstance(s, dict):
                    errors.append(f"{who}: scores {sid} 누락")
                    continue
                lv = s.get("level")
                if lv not in LEVELS + (UNKNOWN,):
                    errors.append(f"{who}: scores {sid} level {lv!r} 이 허용값 아님")
                elif lv != UNKNOWN:
                    if not s.get("evidence"):
                        errors.append(f"{who}: scores {sid} evidence 없음")
                    if not is_url(s.get("source")):
                        errors.append(f"{who}: scores {sid} source URL 없음")
                    if sc_scope == "vertical" and not s.get("division"):
                        errors.append(f"{who}: scores {sid} 는 버티컬별 항목이라 division(근거 사업부) 필요")
            lines = c.get("business_lines")
            if lines is not None and not isinstance(lines, list):
                errors.append(f"{who}: business_lines 는 배열이어야 함")
            for b in lines or []:
                if not isinstance(b, dict) or not b.get("vertical") or not is_url(b.get("source")):
                    errors.append(f"{who}: business_lines 항목에 vertical 과 source URL 필요")
            for r in c.get("contact_roles") or []:
                if not isinstance(r, dict) or not r.get("role"):
                    errors.append(f"{who}: contact_roles 항목에 role 이 없음")
    return errors, units


def load_verify(run_dir):
    out, errors = {}, []
    for path in sorted(glob.glob(os.path.join(run_dir, "verify", "*.json"))):
        data = load_json(path)
        if isinstance(data, Exception):
            errors.append(f"{os.path.basename(path)}: JSON 읽기 실패 ({data})")
            continue
        unit = data.get("unit") or os.path.splitext(os.path.basename(path))[0]
        out.setdefault(unit, {}).update({v.get("company"): v for v in data.get("companies", [])})
    return out, errors


def apply_verify(c, v):
    """Mutate a target record with verifier verdicts. Return drop reason or None."""
    if not v:
        c["_verified"] = False
        return None
    c["_verified"] = True
    if v.get("status") == "drop":
        return f"검증 제외: {v.get('reason') or '사유 미기재'}"
    if is_url(v.get("homepage")):
        c["homepage"] = v["homepage"]
    if isinstance(v.get("summary"), str) and v["summary"].strip():
        c["summary"] = v["summary"].strip()
    for kid, k in (v.get("knockout") or {}).items():
        if isinstance(k, dict) and isinstance(k.get("hit"), bool):
            c.setdefault("knockout", {})[kid] = k
    for sid, it in (v.get("items") or {}).items():
        verdict = it.get("verdict")
        if verdict == "unsupported":
            c.setdefault("scores", {})[sid] = {"level": UNKNOWN, "evidence": "", "source": "",
                                               "note": f"검증 강등: {it.get('reason', '')}"}
        elif verdict == "corrected" and it.get("level") in LEVELS + (UNKNOWN,):
            c.setdefault("scores", {})[sid] = {
                "level": it["level"], "evidence": it.get("evidence", ""), "source": it.get("source", ""),
                "division": it.get("division", c.get("scores", {}).get(sid, {}).get("division", "")),
                "note": "검증 수정"}
    return None


def count_unknown(c, sc_cfg):
    return sum(1 for s in sc_cfg if c["scores"].get(s["id"], {}).get("level", UNKNOWN) == UNKNOWN)


def merge_same_company(a, b, sc_cfg):
    """같은 실행 안에서 두 단위가 찾은 같은 업체를 합친다. 버리지 않고 빈 항목을 서로 채운다."""
    rank = lambda c: (c["_drop"] is None, -c["_unknown"])
    base, other = (a, b) if rank(a) >= rank(b) else (b, a)
    for s in sc_cfg:
        if base["scores"].get(s["id"], {}).get("level", UNKNOWN) == UNKNOWN and \
                other["scores"].get(s["id"], {}).get("level", UNKNOWN) != UNKNOWN:
            base["scores"][s["id"]] = dict(other["scores"][s["id"]], note=f"{other['_unit']} 단위에서 보완")
    for kid, k in (other.get("knockout") or {}).items():
        if k.get("hit") and not base.get("knockout", {}).get(kid, {}).get("hit"):
            base.setdefault("knockout", {})[kid] = k
    seen = {(x.get("vertical"), x.get("division")) for x in base.get("business_lines") or []}
    for x in other.get("business_lines") or []:
        if (x.get("vertical"), x.get("division")) not in seen:
            base.setdefault("business_lines", []).append(x)
    roles = {r["role"] for r in base.get("contact_roles") or []}
    for r in other.get("contact_roles") or []:
        if r["role"] not in roles:
            base.setdefault("contact_roles", []).append(r)
    base["_verified"] = base["_verified"] or other["_verified"]
    base["_dup"] = sorted(set(base.get("_dup", []) + other.get("_dup", []) + [other["_unit"]]))
    base["_unknown"] = count_unknown(base, sc_cfg)
    return base


def compute(run_dir, cfg):
    errors, units = validate_records(run_dir, cfg)
    verify, verrs = load_verify(run_dir)
    errors += verrs
    if errors:
        return errors, None
    ko_cfg = {k["id"]: k for k in cfg["knockout"]}
    sc_cfg = cfg["scoring"]
    merged = {}
    for unit, comps in units.items():
        for c in comps:
            if c["segment"] != "target":
                continue
            c = json.loads(json.dumps(c))  # deep copy
            c["_unit"] = unit
            c["_drop"] = apply_verify(c, verify.get(unit, {}).get(c["company"]))
            c["_unknown"] = count_unknown(c, sc_cfg)
            key = company_key(c)
            c["_key"] = key
            merged[key] = merge_same_company(merged[key], c, sc_cfg) if key in merged else c
    rows = []
    for c in merged.values():
        total, parts = 0, {}
        for s in sc_cfg:
            lv = c["scores"].get(s["id"], {}).get("level", UNKNOWN)
            pts = 0 if lv == UNKNOWN else int(s["levels"][lv])
            parts[s["id"]] = (lv, pts)
            total += pts
        hits = [kid for kid, k in (c.get("knockout") or {}).items() if k.get("hit") and kid in ko_cfg]
        if hits:
            excluded, ex_scope = "Knock-Out: " + ", ".join(f"{h} {ko_cfg[h]['name']}" for h in hits), "company"
        elif c["_drop"]:
            excluded, ex_scope = c["_drop"], "run"
        else:
            excluded, ex_scope = "", ""
        rows.append({"c": c, "total": total, "parts": parts, "excluded": excluded, "ex_scope": ex_scope})
    active = sorted([r for r in rows if not r["excluded"]],
                    key=lambda r: (-r["total"], r["c"]["_unknown"], r["c"]["company"]))
    dropped = sorted([r for r in rows if r["excluded"]], key=lambda r: r["c"]["company"])
    top_n = int(cfg["top_n"])
    for i, r in enumerate(active, 1):
        r["rank"] = i
        flags = []
        if r["c"]["_unknown"] >= 2:
            flags.append("근거부족")
        if abs(i - top_n) <= 5 and len(active) > top_n - 5:
            flags.append("경계")
        if not r["c"]["_verified"]:
            flags.append("미검증")
        pending = [kid for kid, k in (r["c"].get("knockout") or {}).items()
                   if kid in ko_cfg and not k.get("hit") and k.get("uncertain")]
        if pending:
            flags.append(f"KO 미확정({'/'.join(sorted(pending))})")
        r["flags"] = flags
    for r in dropped:
        r["rank"], r["flags"] = "", []
    return [], (active, dropped)


def write_scored(run_dir, cfg, active, dropped):
    """실행 결과를 명부가 읽을 수 있는 scored.json 으로 남긴다."""
    company_ids = [s["id"] for s in cfg["scoring"] if s["scope"] == "company"]
    out = {"vertical": run_vertical(run_dir), "run": os.path.basename(os.path.abspath(run_dir)), "companies": []}
    for r in active + dropped:
        c = r["c"]
        out["companies"].append({
            "key": c["_key"], "company": c["company"], "homepage": c.get("homepage", ""),
            "country": c.get("country", ""), "rank": r["rank"], "total": None if r["excluded"] else r["total"],
            "unknown": c["_unknown"], "excluded": r["excluded"], "excluded_scope": r["ex_scope"],
            "verified": c["_verified"], "business_lines": c.get("business_lines") or [],
            "company_scores": {sid: c["scores"].get(sid, {}) for sid in company_ids},
        })
    with open(os.path.join(run_dir, "scored.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- registry

def build_registry(output_dir, cfg):
    """모든 실행의 scored.json 을 모아 업체 1곳 = 1행 명부를 만든다. {key: entry} 반환."""
    latest = {}  # 같은 버티컬을 다시 돌렸으면 가장 최근 실행만 쓴다
    dirs = [os.path.dirname(p) for p in glob.glob(os.path.join(output_dir, "*", "scored.json"))
            if os.path.basename(os.path.dirname(p)) != REGISTRY]
    for d in sorted(dirs, key=lambda d: (run_created(d), d)):
        data = load_json(os.path.join(d, "scored.json"))
        if isinstance(data, dict):
            data["_dir"], data["_order"] = d, run_created(d)
            latest[data.get("vertical")] = data
    runs = sorted(latest.values(), key=lambda r: (r["_order"], r["run"]))
    company_ids = [s["id"] for s in cfg["scoring"] if s["scope"] == "company"]
    reg = {}
    for run in runs:
        for c in run["companies"]:
            c["key"] = company_key(c)            # 예전 실행이 저장한 키는 규칙이 바뀌었을 수 있어 다시 계산한다
            e = reg.setdefault(c["key"], {"key": c["key"], "company": c["company"], "homepage": c["homepage"],
                                         "entries": [], "lines": [], "facts": {}})
            e["entries"].append(dict(c, vertical=run["vertical"], run=run["run"], order=run["_order"]))
            e["lines"] += c.get("business_lines") or []
            for sid in company_ids:
                s = c["company_scores"].get(sid) or {}
                if s.get("level", UNKNOWN) != UNKNOWN and (sid not in e["facts"] or c["verified"]):
                    e["facts"][sid] = dict(s, run=run["run"], verified=c["verified"])
    # 홈페이지 없이 이름으로 잡힌 업체가 다른 실행에서 홈페이지와 함께 나왔으면 하나로 합친다
    by_name = {name_key(x["company"]): e for e in reg.values() if "." in e["key"] for x in e["entries"]}
    for k in [k for k in reg if "." not in k]:
        host = by_name.get(k)
        if host:
            e = reg.pop(k)
            host["entries"] += e["entries"]
            host["lines"] += e["lines"]
            for sid, v in e["facts"].items():
                host["facts"].setdefault(sid, v)
            host.setdefault("aliases", set()).add(k)
    for e in reg.values():
        # Knock-Out 은 회사 단위다. 회사 단위 판정을 내린 실행 가운데 가장 최근 것을 따른다
        judged = [x for x in e["entries"] if x["excluded_scope"] != "run"]
        last = max(judged, key=lambda x: x["order"]) if judged else None
        active = [x for x in e["entries"] if not x["excluded"]]
        researched = {x["vertical"] for x in e["entries"]}
        e["excluded"] = last["excluded"] + f" ({last['vertical']})"             if last and last["excluded_scope"] == "company" else ""
        # 동점이면 확인불가가 적은 쪽, 그다음 먼저 실행한 버티컬
        e["active"] = sorted(active, key=lambda x: (-x["total"], x["unknown"], x["order"], x["vertical"]))
        e["primary"] = None if e["excluded"] or not e["active"] else e["active"][0]
        e["declared"] = sorted({b["vertical"] for b in e["lines"] if b["vertical"] not in researched})
        e["multi"] = len({x["vertical"] for x in e["active"]}) > 1 or bool(e["declared"])
        flags = []
        for sid in company_ids:
            levels = {x["company_scores"].get(sid, {}).get("level") for x in e["entries"]} - {None, UNKNOWN}
            if len(levels) > 1:
                flags.append(f"{sid} 회사공통 불일치({'/'.join(sorted(levels))})")
        ko_runs = [x for x in judged if x["excluded_scope"] == "company"]
        if ko_runs and last["excluded_scope"] != "company":
            flags.append(f"KO 판정 변경({ko_runs[-1]['vertical']} 제외 → {last['vertical']} 해당 없음)")
        e["flags"] = flags
    return reg, runs


def write_registry(output_dir, cfg, reg):
    d = os.path.join(output_dir, REGISTRY)
    os.makedirs(d, exist_ok=True)
    head = ["company", "homepage", "proposal_vertical", "proposal_score", "proposal_rank", "other_verticals",
            "declared_other_lines", "multi_vertical", "excluded", "flags", "runs"]
    ordered = sorted(reg.values(), key=lambda e: (e["primary"] is None,
                                                  -(e["primary"]["total"] if e["primary"] else 0), e["company"]))
    with open(os.path.join(d, "companies.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        for e in ordered:
            p = e["primary"]
            w.writerow([e["company"], e["homepage"], p["vertical"] if p else "", p["total"] if p else "",
                        p["rank"] if p else "",
                        "; ".join(f"{x['vertical']}({x['total']})" for x in e["active"][1:]) if p else "",
                        "; ".join(e["declared"]), "Y" if e["multi"] else "", e["excluded"],
                        "; ".join(e["flags"]), "; ".join(x["run"] for x in e["entries"])])
    facts = {e["key"]: {"company": e["company"], "homepage": e["homepage"], "items": e["facts"]}
             for e in reg.values() if e["facts"]}
    with open(os.path.join(d, "company_facts.json"), "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=1)
    proposals = [e for e in ordered if e["primary"]]
    multi = [e for e in proposals if e["multi"]]
    lines = ["# 업체 명부 요약 (gate.py 생성 — 직접 수정 금지)", "",
             f"- 전체 업체 {len(reg)}곳 · 제안 대상 {len(proposals)}곳 (업체당 제안서 1건) · 제외 {len(reg) - len(proposals)}곳",
             f"- 여러 버티컬에 걸친 업체 {len(multi)}곳", "",
             "| 업체 | 제안 버티컬 | 점수 | 함께 제안할 버티컬 |", "|---|---|---|---|"]
    for e in multi:
        others = [f"{x['vertical']}({x['total']})" for x in e["active"][1:]] + [f"{v}(미조사)" for v in e["declared"]]
        lines.append(f"| {e['company']} | {e['primary']['vertical']} | {e['primary']['total']} | {', '.join(others)} |")
    with open(os.path.join(d, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_outputs(run_dir, cfg, active, dropped, reg):
    sc_cfg = cfg["scoring"]
    top_n = int(cfg["top_n"])
    vertical = run_vertical(run_dir)
    for r in active + dropped:
        key = r["c"]["_key"]
        e = reg.get(key) or next((x for x in reg.values() if key in x.get("aliases", ())), {})
        p = e.get("primary")
        r["proposal_vertical"] = p["vertical"] if p else ""
        r["others"] = [f"{x['vertical']}({x['total']})" for x in e.get("active", []) if x["vertical"] != vertical] + \
                      [f"{v}(미조사)" for v in e.get("declared", [])]
        if r["rank"] and p and p["vertical"] != vertical:
            r["flags"].append("타버티컬제안")
        if r["rank"] and e.get("excluded"):
            r["flags"].append("타버티컬KO")
        r["flags"] += e.get("flags", [])
    head = ["rank", "top_n", "company", "country", "homepage", "unit", "total"] + \
           [s["id"] for s in sc_cfg] + ["unknown_count", "review_flag", "proposal_vertical", "other_verticals",
                                       "excluded", "contact_roles", "summary"]
    with open(os.path.join(run_dir, "candidates.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        for r in active + dropped:
            c = r["c"]
            w.writerow([r["rank"], "Y" if r["rank"] and r["rank"] <= top_n else "", c["company"],
                        c.get("country", ""), c.get("homepage", ""), c["_unit"], "" if r["excluded"] else r["total"]] +
                       [f"{r['parts'][s['id']][0]}({r['parts'][s['id']][1]})" for s in sc_cfg] +
                       [c["_unknown"], ",".join(r["flags"]), r["proposal_vertical"], "; ".join(r["others"]),
                        r["excluded"], "; ".join(x["role"] for x in c.get("contact_roles") or []), c.get("summary", "")])
    lines = ["# 채점 근거 (gate.py 생성 — 직접 수정 금지)", "",
             f"- 버티컬: {vertical}",
             f"- 채점 대상 {len(active) + len(dropped)}곳 · 제외 {len(dropped)}곳 · 순위 {len(active)}곳 · Top {top_n}", ""]
    for r in active + dropped:
        c = r["c"]
        title = f"{r['rank']}. {c['company']}" if r["rank"] else f"(제외) {c['company']}"
        lines += [f"## {title}", ""]
        meta = [f"홈페이지: {c.get('homepage', '')}", f"단위: {c['_unit']}"]
        if c.get("_dup"):
            meta.append(f"함께 발견한 단위: {', '.join(c['_dup'])}")
        meta.append(f"제외 사유: {r['excluded']}" if r["excluded"] else f"합계: **{r['total']}점**")
        if r["proposal_vertical"]:
            meta.append(f"제안 버티컬: {r['proposal_vertical']}")
        if r["others"]:
            meta.append(f"다른 버티컬: {', '.join(r['others'])}")
        if r["flags"]:
            meta.append(f"검토 표시: {', '.join(r['flags'])}")
        lines += [" · ".join(meta), "", "| 항목 | 범위 | 등급 | 점수 | 근거 | 사업부 | 출처 |", "|---|---|---|---|---|---|---|"]
        for s in sc_cfg:
            sc = c["scores"].get(s["id"], {})
            lv, pts = r["parts"][s["id"]]
            ev = (sc.get("evidence") or "") + (f" ({sc['note']})" if sc.get("note") else "")
            lines.append(f"| {s['id']} {s['name']} | {'회사' if s['scope'] == 'company' else '버티컬'} | {lv} | "
                         f"{pts}/{s['max']} | {ev.replace('|', '/')} | {sc.get('division', '')} | {sc.get('source', '')} |")
        lines.append("")
    with open(os.path.join(run_dir, "evidence.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def refresh_runs(cfg, reg, runs, skip=None):
    """명부가 바뀌면 다른 실행의 candidates.csv·evidence.md 도 새 명부 기준으로 다시 쓴다.
    점수는 그대로이고 제안 버티컬·다른 버티컬·검토 표시만 바뀐다. 반환: 다시 쓴 실행 이름 목록."""
    done = []
    for run in runs:
        d = run["_dir"]
        if skip and os.path.normcase(os.path.abspath(d)) == os.path.normcase(os.path.abspath(skip)):
            continue
        rcfg = run_config(d, cfg)
        errors, res = compute(d, rcfg)
        if errors:
            print(f"WARN: {run['run']} 다시 쓰기 건너뜀 ({len(errors)}건 오류)")
            continue
        write_outputs(d, rcfg, *res, reg)
        done.append(run["run"])
    return done


# ---------------------------------------------------------------- commands

def print_errors(title, errors):
    print(f"FAIL {title}: {len(errors)}건")
    for e in errors:
        print(" -", e)


def cmd_check_records(args, cfg):
    errors, units = validate_records(args.dir, cfg)
    if errors:
        print_errors("check-records", errors)
        return 1
    n = sum(len(v) for v in units.values())
    t = sum(1 for v in units.values() for c in v if c["segment"] == "target")
    print(f"PASS check-records: 단위 {len(units)}개 · 업체 {n}곳 (target {t})")
    countries = run_countries(args.dir)
    if countries:
        # 지역 밖 업체는 실패로 막지 않는다 — 지역 법인이 있는 외국 업체일 수 있어 사람이 본다
        outside = [f"{c['company']} ({c.get('country') or '국가 없음'})" for v in units.values() for c in v
                   if c["segment"] == "target" and (c.get("country") or "").upper() not in countries]
        if outside:
            print(f"WARN: 조사 지역 밖 target {len(outside)}곳 — {', '.join(outside)}")
    return 0


def cmd_score(args, cfg):
    errors, res = compute(args.dir, cfg)
    if errors:
        print_errors("score", errors)
        return 1
    active, dropped = res
    write_scored(args.dir, cfg, active, dropped)
    output_dir = os.path.dirname(os.path.abspath(os.path.normpath(args.dir)))
    reg, runs = build_registry(output_dir, cfg)
    write_registry(output_dir, cfg, reg)
    write_outputs(args.dir, cfg, active, dropped, reg)
    refreshed = refresh_runs(cfg, reg, runs, skip=args.dir)
    top_n = int(cfg["top_n"])
    flagged = sum(1 for r in active if r["flags"])
    multi = sum(1 for r in active if r["others"])
    print(f"PASS score: 순위 {len(active)}곳 · 제외 {len(dropped)}곳 · 검토 표시 {flagged}곳 · 다중 버티컬 {multi}곳")
    print(f"명부: {os.path.join(output_dir, REGISTRY)} (전체 {len(reg)}곳)")
    if refreshed:
        print(f"다른 실행 갱신: {', '.join(refreshed)} (candidates.csv·evidence.md)")
    if len(active) < top_n:
        print(f"WARN: 순위 업체 {len(active)}곳 < top_n {top_n} — 추가 조사 필요")
        return 1
    return 0


def cmd_registry(args, cfg):
    reg, runs = build_registry(args.dir, cfg)
    if not reg:
        print("FAIL registry: scored.json 이 있는 실행 폴더가 없음")
        return 1
    write_registry(args.dir, cfg, reg)
    refreshed = refresh_runs(cfg, reg, runs)
    if refreshed:
        print(f"실행 갱신: {', '.join(refreshed)} (candidates.csv·evidence.md)")
    n = sum(1 for e in reg.values() if e["primary"])
    print(f"PASS registry: 전체 {len(reg)}곳 · 제안 대상 {n}곳 · 다중 버티컬 {sum(1 for e in reg.values() if e['multi'] and e['primary'])}곳")
    return 0


def read_top_names(run_dir, top_n):
    path = os.path.join(run_dir, "candidates.csv")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig") as f:
        return [row["company"] for row in csv.DictReader(f) if row["top_n"] == "Y"][:top_n]


def cmd_check_report(args, cfg):
    path = os.path.join(args.dir, "report.md")
    if not os.path.exists(path):
        print("FAIL check-report: report.md 없음")
        return 1
    with open(path, encoding="utf-8") as f:
        text = f.read()
    names = read_top_names(args.dir, int(cfg["top_n"]))
    if names is None:
        print("FAIL check-report: candidates.csv 없음 (score 먼저)")
        return 1
    missing = [n for n in names if n not in text]
    if missing:
        print_errors("check-report: Top N 업체가 본문에 없음", missing)
        return 1
    print(f"PASS check-report: Top {len(names)} 전원 본문 포함")
    return 0


def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def cmd_check_ko(args):
    data = load_json(os.path.join(args.dir, "ko_review.json"))
    if isinstance(data, Exception):
        print(f"FAIL check-ko: ko_review.json 읽기 실패 ({data})")
        return 1
    try:
        with open(os.path.join(args.dir, "report.md"), encoding="utf-8") as f:
            report = norm_ws(f.read())
    except OSError:
        print("FAIL check-ko: report.md 없음")
        return 1
    findings = data.get("findings")
    if not isinstance(findings, list):
        print("FAIL check-ko: findings 배열 없음")
        return 1
    bad, count = [], {s: 0 for s in SEVERITIES}
    for i, fd in enumerate(findings):
        sev = fd.get("severity")
        if sev not in SEVERITIES:
            bad.append(f"#{i}: severity {sev!r} 허용값 아님")
            continue
        q = norm_ws(fd.get("quote") or "")
        if not q or q not in report:
            bad.append(f"#{i} [{sev}]: quote 가 report.md 에 없음 → {q[:40]!r}")
            continue
        count[sev] += 1
    summary = " · ".join(f"{s} {count[s]}" for s in SEVERITIES)
    if bad:
        print_errors(f"check-ko: 잘못된 지적 ({summary})", bad)
        return 1
    if count["S1"]:
        print(f"FAIL check-ko: S1 {count['S1']}건 남음 ({summary})")
        for fd in findings:
            if fd.get("severity") == "S1":
                print(f" - {fd.get('issue', '')}: {norm_ws(fd.get('quote', ''))[:60]}")
        return 1
    print(f"PASS check-ko: {summary}")
    return 0


def cmd_new_run(args):
    """실행 폴더를 만들고 경로를 출력한다. 같은 이름이 있으면 -2, -3 을 붙인다 (이전 실행을 덮어쓰지 않는다)."""
    today = datetime.date.today()
    base = os.path.join(args.dir, run_folder_name(args.vertical, today.strftime("%Y%m%d")))
    path, n = base, 1
    while os.path.exists(path):
        n += 1
        path = f"{base}-{n}"
    for sub in ("notes", "records", "verify"):
        os.makedirs(os.path.join(path, sub))
    regions = [r.strip() for r in (args.regions or "").split(",") if r.strip()]
    meta = {"vertical": args.vertical.strip(), "regions": regions, "date": today.isoformat(),
            "created": datetime.datetime.now().isoformat(timespec="seconds")}
    # 대륙 지역(설정의 region_groups)은 국가 코드로 풀어 둔다. 설정에 없는 지역(Korea 등)은 이름만 남는다
    groups = load_config(args.config)["region_groups"] if args.config else {}
    countries = [c.upper() for r in regions for c in groups.get(r, [])]
    if countries:
        meta["countries"] = sorted(set(countries))
    with open(os.path.join(path, "run.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(os.path.abspath(path))
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="vertical-research gate")
    p.add_argument("command", choices=["new-run", "check-records", "score", "registry", "check-report", "check-ko"])
    p.add_argument("dir", help="실행 폴더 (registry 는 output_dir)")
    p.add_argument("--config")
    p.add_argument("--vertical", help="new-run: 버티컬 표기")
    p.add_argument("--regions", help="new-run: 쉼표로 구분한 지역 (설정의 region_groups 이름이면 국가 코드로 풀린다)")
    args = p.parse_args()
    if args.command == "new-run":
        if not args.vertical or not args.vertical.strip():
            die("--vertical 이 필요함")
        os.makedirs(args.dir, exist_ok=True)
        sys.exit(cmd_new_run(args))
    if not os.path.isdir(args.dir):
        die(f"폴더가 없음: {args.dir}")
    if args.command == "check-ko":
        sys.exit(cmd_check_ko(args))
    if not args.config:
        die("--config 가 필요함")
    cfg = load_config(args.config)
    sys.exit({"check-records": cmd_check_records, "score": cmd_score, "registry": cmd_registry,
              "check-report": cmd_check_report}[args.command](args, cfg))


if __name__ == "__main__":
    main()
