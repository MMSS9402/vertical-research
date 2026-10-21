#!/usr/bin/env python3
"""vertical-research gate: 산출물 형식 검사, Knock-Out·채점·순위 계산.

Usage:
  gate.py check-records <run_dir> --config <config.md>
  gate.py score         <run_dir> --config <config.md>
  gate.py check-report  <run_dir> --config <config.md>
  gate.py check-ko      <run_dir>

Exit code 0 = pass, 1 = gate fail, 2 = usage/config error. 표준 라이브러리만 쓴다.
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from urllib.parse import urlparse

LEVELS = ("상", "중", "하")
UNKNOWN = "확인불가"
SEVERITIES = ("S1", "S2", "S3")


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
    return cfg


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return e


def is_url(s):
    return isinstance(s, str) and re.match(r"https?://\S+", s) is not None


def company_key(c):
    host = urlparse(c.get("homepage") or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host:
        return host
    return re.sub(r"[^0-9a-z가-힣]", "", (c.get("company") or "").lower())


def records_files(run_dir):
    return sorted(glob.glob(os.path.join(run_dir, "records", "*.json")))


def validate_records(run_dir, cfg):
    """Return (errors, records_by_unit)."""
    errors, units = [], {}
    ko_ids = [k["id"] for k in cfg["knockout"]]
    sc_ids = [s["id"] for s in cfg["scoring"]]
    files = records_files(run_dir)
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
            for sid in sc_ids:
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
        out[unit] = {v.get("company"): v for v in data.get("companies", [])}
    return out, errors


def apply_verify(c, v):
    """Mutate a target record with verifier verdicts. Return drop reason or None."""
    if not v:
        c["_verified"] = False
        return None
    c["_verified"] = True
    if v.get("status") == "drop":
        return f"검증 제외: {v.get('reason') or '사유 미기재'}"
    for kid, k in (v.get("knockout") or {}).items():
        if isinstance(k, dict) and isinstance(k.get("hit"), bool):
            c.setdefault("knockout", {})[kid] = k
    for sid, it in (v.get("items") or {}).items():
        s = c.setdefault("scores", {}).setdefault(sid, {})
        verdict = it.get("verdict")
        if verdict == "unsupported":
            c["scores"][sid] = {"level": UNKNOWN, "evidence": "", "source": "",
                                "note": f"검증 강등: {it.get('reason', '')}"}
        elif verdict == "corrected" and it.get("level") in LEVELS + (UNKNOWN,):
            c["scores"][sid] = {"level": it["level"], "evidence": it.get("evidence", ""),
                                "source": it.get("source", ""), "note": "검증 수정"}
    return None


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
            c["_unknown"] = sum(1 for s in sc_cfg if c["scores"].get(s["id"], {}).get("level") == UNKNOWN)
            key = company_key(c)
            prev = merged.get(key)
            if prev is None or (c["_drop"] is None, -c["_unknown"]) > (prev["_drop"] is None, -prev["_unknown"]):
                if prev is not None:
                    c["_dup"] = sorted(set(prev.get("_dup", []) + [prev["_unit"]]))
                merged[key] = c
            else:
                prev.setdefault("_dup", []).append(unit)
    rows = []
    for c in merged.values():
        total, parts = 0, {}
        for s in sc_cfg:
            lv = c["scores"].get(s["id"], {}).get("level", UNKNOWN)
            pts = 0 if lv == UNKNOWN else int(s["levels"][lv])
            parts[s["id"]] = (lv, pts)
            total += pts
        hits = [kid for kid, k in (c.get("knockout") or {}).items() if k.get("hit") and kid in ko_cfg]
        excluded = c["_drop"] or (("Knock-Out: " + ", ".join(f"{h} {ko_cfg[h]['name']}" for h in hits)) if hits else "")
        rows.append({"c": c, "total": total, "parts": parts, "excluded": excluded})
    active = sorted([r for r in rows if not r["excluded"]], key=lambda r: (-r["total"], r["c"]["_unknown"], r["c"]["company"]))
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
        r["flag"] = ",".join(flags)
    for r in dropped:
        r["rank"], r["flag"] = "", ""
    return [], (active, dropped)


def write_outputs(run_dir, cfg, active, dropped):
    sc_cfg = cfg["scoring"]
    top_n = int(cfg["top_n"])
    head = ["rank", "top_n", "company", "country", "homepage", "unit", "total"] + \
           [s["id"] for s in sc_cfg] + ["unknown_count", "review_flag", "excluded", "contact_roles", "summary"]
    with open(os.path.join(run_dir, "candidates.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        for r in active + dropped:
            c = r["c"]
            w.writerow([r["rank"], "Y" if r["rank"] and r["rank"] <= top_n else "", c["company"],
                        c.get("country", ""), c.get("homepage", ""), c["_unit"], "" if r["excluded"] else r["total"]] +
                       [f"{r['parts'][s['id']][0]}({r['parts'][s['id']][1]})" for s in sc_cfg] +
                       [c["_unknown"], r["flag"], r["excluded"],
                        "; ".join(x["role"] for x in c.get("contact_roles") or []), c.get("summary", "")])
    lines = ["# 채점 근거 (gate.py 생성 — 직접 수정 금지)", "",
             f"- 채점 대상 {len(active) + len(dropped)}곳 · 제외 {len(dropped)}곳 · 순위 {len(active)}곳 · Top {top_n}", ""]
    for r in active + dropped:
        c = r["c"]
        title = f"{r['rank']}. {c['company']}" if r["rank"] else f"(제외) {c['company']}"
        lines += [f"## {title}", ""]
        meta = [f"홈페이지: {c.get('homepage', '')}", f"단위: {c['_unit']}"]
        if c.get("_dup"):
            meta.append(f"중복 발견: {', '.join(c['_dup'])}")
        if r["excluded"]:
            meta.append(f"제외 사유: {r['excluded']}")
        else:
            meta.append(f"합계: **{r['total']}점**")
        if r["flag"]:
            meta.append(f"검토 표시: {r['flag']}")
        lines += [" · ".join(meta), "", "| 항목 | 등급 | 점수 | 근거 | 출처 |", "|---|---|---|---|---|"]
        for s in sc_cfg:
            sc = c["scores"].get(s["id"], {})
            lv, pts = r["parts"][s["id"]]
            ev = (sc.get("evidence") or "") + (f" ({sc['note']})" if sc.get("note") else "")
            lines.append(f"| {s['id']} {s['name']} | {lv} | {pts}/{s['max']} | {ev.replace('|', '/')} | {sc.get('source', '')} |")
        lines.append("")
    with open(os.path.join(run_dir, "evidence.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def cmd_check_records(args, cfg):
    errors, units = validate_records(args.run_dir, cfg)
    if errors:
        print(f"FAIL check-records: {len(errors)}건")
        for e in errors:
            print(" -", e)
        return 1
    n = sum(len(v) for v in units.values())
    t = sum(1 for v in units.values() for c in v if c["segment"] == "target")
    print(f"PASS check-records: 단위 {len(units)}개 · 업체 {n}곳 (target {t})")
    return 0


def cmd_score(args, cfg):
    errors, res = compute(args.run_dir, cfg)
    if errors:
        print(f"FAIL score: 형식 오류 {len(errors)}건")
        for e in errors:
            print(" -", e)
        return 1
    active, dropped = res
    write_outputs(args.run_dir, cfg, active, dropped)
    top_n = int(cfg["top_n"])
    flagged = sum(1 for r in active if r["flag"])
    print(f"PASS score: 순위 {len(active)}곳 · 제외 {len(dropped)}곳 · 검토 표시 {flagged}곳")
    if len(active) < top_n:
        print(f"WARN: 순위 업체 {len(active)}곳 < top_n {top_n} — 추가 조사 필요")
        return 1
    return 0


def read_top_names(run_dir, top_n):
    path = os.path.join(run_dir, "candidates.csv")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig") as f:
        return [row["company"] for row in csv.DictReader(f) if row["top_n"] == "Y"][:top_n]


def cmd_check_report(args, cfg):
    path = os.path.join(args.run_dir, "report.md")
    if not os.path.exists(path):
        print("FAIL check-report: report.md 없음")
        return 1
    with open(path, encoding="utf-8") as f:
        text = f.read()
    names = read_top_names(args.run_dir, int(cfg["top_n"]))
    if names is None:
        print("FAIL check-report: candidates.csv 없음 (score 먼저)")
        return 1
    missing = [n for n in names if n not in text]
    if missing:
        print(f"FAIL check-report: Top N 업체 {len(missing)}곳이 본문에 없음")
        for n in missing:
            print(" -", n)
        return 1
    print(f"PASS check-report: Top {len(names)} 전원 본문 포함")
    return 0


def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def cmd_check_ko(args):
    rpath = os.path.join(args.run_dir, "report.md")
    kpath = os.path.join(args.run_dir, "ko_review.json")
    data = load_json(kpath)
    if isinstance(data, Exception):
        print(f"FAIL check-ko: ko_review.json 읽기 실패 ({data})")
        return 1
    try:
        with open(rpath, encoding="utf-8") as f:
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
        print(f"FAIL check-ko: 잘못된 지적 {len(bad)}건 ({summary})")
        for b in bad:
            print(" -", b)
        return 1
    if count["S1"]:
        print(f"FAIL check-ko: S1 {count['S1']}건 남음 ({summary})")
        for fd in findings:
            if fd.get("severity") == "S1":
                print(f" - {fd.get('issue', '')}: {norm_ws(fd.get('quote', ''))[:60]}")
        return 1
    print(f"PASS check-ko: {summary}")
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="vertical-research gate")
    p.add_argument("command", choices=["check-records", "score", "check-report", "check-ko"])
    p.add_argument("run_dir")
    p.add_argument("--config")
    args = p.parse_args()
    if not os.path.isdir(args.run_dir):
        die(f"실행 폴더가 없음: {args.run_dir}")
    if args.command == "check-ko":
        sys.exit(cmd_check_ko(args))
    if not args.config:
        die("--config 가 필요함")
    cfg = load_config(args.config)
    sys.exit({"check-records": cmd_check_records, "score": cmd_score,
              "check-report": cmd_check_report}[args.command](args, cfg))


if __name__ == "__main__":
    main()
