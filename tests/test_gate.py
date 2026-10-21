"""gate.py 단위 테스트. 실행: python -m unittest discover -s tests"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(ROOT, "scripts", "gate.py")
CONFIG = os.path.join(ROOT, "examples", "vertical-research.config.md")
SCORING = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2"]
KO = ["K1", "K2", "K3", "K4"]


def target(name, home, levels, ko_hit=None):
    return {
        "company": name, "homepage": home, "country": "KR", "segment": "target", "summary": "s",
        "knockout": {k: ({"hit": True, "evidence": "e", "source": "https://x.com/k"} if k == ko_hit
                         else {"hit": False, "evidence": "", "source": ""}) for k in KO},
        "scores": {sid: ({"level": lv, "evidence": f"{sid} 근거", "source": f"https://x.com/{sid}", "division": "전사"}
                         if lv != "확인불가" else {"level": lv, "evidence": "", "source": ""})
                   for sid, lv in zip(SCORING, levels)},
        "contact_roles": [{"role": "Head of Product", "source": "https://x.com/team"}],
    }


def run(*args):
    p = subprocess.run([sys.executable, GATE, *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


class GateTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()          # output_dir 역할
        self.dir = self.make_run("run1", "건설")
        # top_n 을 3 으로 줄인 설정
        with open(CONFIG, encoding="utf-8") as f:
            text = f.read().replace('"top_n": 20', '"top_n": 3')
        self.cfg = os.path.join(self.root, "cfg.md")
        with open(self.cfg, "w", encoding="utf-8") as f:
            f.write(text)

    def tearDown(self):
        shutil.rmtree(self.root)

    def make_run(self, name, vertical):
        d = os.path.join(self.root, name)
        for sub in ("records", "verify"):
            os.makedirs(os.path.join(d, sub))
        with open(os.path.join(d, "run.json"), "w", encoding="utf-8") as f:
            json.dump({"vertical": vertical}, f, ensure_ascii=False)
        return d

    def write(self, rel, data, run_dir=None):
        with open(os.path.join(run_dir or self.dir, rel), "w", encoding="utf-8") as f:
            if isinstance(data, str):
                f.write(data)
            else:
                json.dump(data, f, ensure_ascii=False)

    def rows(self, run_dir=None):
        with open(os.path.join(run_dir or self.dir, "candidates.csv"), encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def base_records(self):
        top = ["상"] * 8                     # 100
        mid = ["중"] * 8                     # 10+6+10+10+10+6+6+6 = 64
        low = ["하"] * 7 + ["확인불가"]       # 5+2+0+0+5+2+2+0 = 16, unknown 1
        self.write("records/u1.json", {"unit": "u1", "companies": [
            target("Alpha", "https://www.alpha.com", top),
            target("Beta", "https://beta.com", mid),
            target("Gamma", "https://gamma.com", low),
            target("Rival", "https://rival.com", top, ko_hit="K1"),
            {"company": "CompetitorX", "homepage": "https://cx.com", "segment": "competitor"},
        ]})
        self.write("records/u2.json", {"unit": "u2", "companies": [
            target("Delta", "https://delta.com", ["중"] * 6 + ["확인불가"] * 2),
            target("Alpha Inc", "https://alpha.com/en", ["상"] * 6 + ["확인불가"] * 2),
        ]})

    def test_config_parses_and_missing_records_fails(self):
        code, out = run("check-records", self.dir, "--config", self.cfg)
        self.assertEqual(code, 1)
        self.assertIn("records", out)

    def test_check_records_pass(self):
        self.base_records()
        code, out = run("check-records", self.dir, "--config", self.cfg)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_check_records_catches_missing_source_and_item(self):
        rec = target("Bad", "https://bad.com", ["상"] * 8)
        rec["scores"]["A1"]["source"] = ""
        del rec["scores"]["D2"]
        rec["knockout"]["K2"] = {"hit": "no"}
        self.write("records/u1.json", {"unit": "u1", "companies": [rec]})
        code, out = run("check-records", self.dir, "--config", self.cfg)
        self.assertEqual(code, 1)
        self.assertIn("A1 source URL 없음", out)
        self.assertIn("D2 누락", out)
        self.assertIn("K2", out)

    def test_score_ranks_knockout_and_dedup(self):
        self.base_records()
        code, out = run("score", self.dir, "--config", self.cfg)
        self.assertEqual(code, 0, out)
        rows = self.rows()
        ranked = [r for r in rows if r["rank"]]
        self.assertEqual([r["company"] for r in ranked], ["Alpha", "Beta", "Delta", "Gamma"])
        self.assertEqual(ranked[0]["total"], "100")
        self.assertEqual(ranked[1]["total"], "64")
        self.assertEqual(ranked[2]["total"], "52")  # 중 6개: 10+6+10+10+10+6
        self.assertEqual([r["top_n"] for r in ranked], ["Y", "Y", "Y", ""])
        rival = next(r for r in rows if r["company"] == "Rival")
        self.assertIn("K1", rival["excluded"])
        self.assertNotIn("CompetitorX", [r["company"] for r in rows])
        self.assertNotIn("Alpha Inc", [r["company"] for r in rows])  # alpha.com 중복 → 확인불가 적은 Alpha 유지
        self.assertIn("근거부족", next(r for r in rows if r["company"] == "Delta")["review_flag"])
        self.assertIn("미검증", ranked[0]["review_flag"])
        self.assertTrue(os.path.exists(os.path.join(self.dir, "evidence.md")))

    def test_verify_applies_drop_correct_unsupported(self):
        self.base_records()
        self.write("verify/u1.json", {"unit": "u1", "companies": [
            {"company": "Alpha", "status": "fix", "items": {
                "A1": {"verdict": "unsupported", "reason": "출처에 없음"},
                "D1": {"verdict": "corrected", "level": "하", "evidence": "2건", "source": "https://alpha.com/c"}}},
            {"company": "Beta", "status": "drop", "reason": "실존 확인 불가"},
            {"company": "Gamma", "status": "fix", "knockout": {"K2": {"hit": True, "evidence": "유통", "source": "https://g.com"}}},
        ]})
        code, out = run("score", self.dir, "--config", self.cfg)
        rows = {r["company"]: r for r in self.rows()}
        # A1 은 검증에서 강등됐지만 같은 업체를 찾은 u2(Alpha Inc) 기록으로 보완된다
        self.assertEqual(rows["Alpha"]["total"], str(100 - 8))
        self.assertEqual(rows["Alpha"]["A1"], "상(15)")
        with open(os.path.join(self.dir, "evidence.md"), encoding="utf-8") as f:
            self.assertIn("u2 단위에서 보완", f.read())
        self.assertEqual(rows["Alpha"]["D1"], "하(2)")
        self.assertNotIn("미검증", rows["Alpha"]["review_flag"])
        self.assertIn("검증 제외", rows["Beta"]["excluded"])
        self.assertIn("K2", rows["Gamma"]["excluded"])
        # 순위 업체 2곳 < top_n 3 → 추가 조사 신호
        self.assertEqual(code, 1)
        self.assertIn("WARN", out)

    def test_verify_homepage_correction_feeds_merge(self):
        self.base_records()
        run("score", self.dir, "--config", self.cfg)
        n_before = len(self.rows())
        self.write("verify/u2.json", {"unit": "u2", "companies": [
            {"company": "Delta", "status": "fix", "homepage": "https://www.beta.com/ko"},
            {"company": "Alpha Inc", "status": "ok"},
            {"company": "Ghost", "status": "fix", "homepage": "기사 링크"},
        ]})
        run("score", self.dir, "--config", self.cfg)
        rows = self.rows()
        # Delta 의 홈페이지가 beta.com 으로 고쳐져 Beta 와 같은 업체로 합쳐진다
        self.assertEqual(len(rows), n_before - 1)
        merged = [r for r in rows if r["company"] in ("Beta", "Delta")]
        self.assertEqual(len(merged), 1)
        self.assertIn("beta.com", merged[0]["homepage"])

    def test_verify_summary_correction(self):
        self.base_records()
        self.write("verify/u1.json", {"unit": "u1", "companies": [
            {"company": "Beta", "status": "fix", "summary": "검증 후 요약"},
            {"company": "Gamma", "status": "ok", "summary": "  "},
        ]})
        run("score", self.dir, "--config", self.cfg)
        rows = {r["company"]: r for r in self.rows()}
        self.assertEqual(rows["Beta"]["summary"], "검증 후 요약")
        self.assertNotEqual(rows["Gamma"]["summary"], "")

    def test_check_report(self):
        self.base_records()
        run("score", self.dir, "--config", self.cfg)
        self.write("report.md", "# 보고서\nAlpha 와 Beta 를 추천한다.")
        code, out = run("check-report", self.dir, "--config", self.cfg)
        self.assertEqual(code, 1)
        self.assertIn("Delta", out)
        self.write("report.md", "# 보고서\nAlpha, Beta, Delta 순으로 제안한다.")
        code, out = run("check-report", self.dir, "--config", self.cfg)
        self.assertEqual(code, 0, out)

    def test_check_ko(self):
        self.write("report.md", "이 솔루션은 출입통제에 있어서 중요한 역할을 한다.\n다음  문장은   괜찮다.")
        self.write("ko_review.json", {"findings": [
            {"severity": "S1", "quote": "출입통제에 있어서", "issue": "번역체", "fix": "출입통제에서"}]})
        code, out = run("check-ko", self.dir)
        self.assertEqual(code, 1)
        self.assertIn("S1 1건", out)
        self.write("ko_review.json", {"findings": [
            {"severity": "S2", "quote": "다음 문장은 괜찮다", "issue": "x", "fix": "y"}]})
        code, out = run("check-ko", self.dir)
        self.assertEqual(code, 0, out)
        self.write("ko_review.json", {"findings": [
            {"severity": "S2", "quote": "본문에 없는 문장", "issue": "x", "fix": "y"}]})
        code, out = run("check-ko", self.dir)
        self.assertEqual(code, 1)
        self.assertIn("quote 가 report.md 에 없음", out)


    def test_vertical_item_requires_division(self):
        rec = target("NoDiv", "https://nodiv.com", ["상"] * 8)
        del rec["scores"]["B1"]["division"]
        del rec["scores"]["A1"]["division"]   # 회사 공통 항목은 division 없어도 됨
        rec["business_lines"] = [{"vertical": "오피스"}]
        self.write("records/u1.json", {"unit": "u1", "companies": [rec]})
        code, out = run("check-records", self.dir, "--config", self.cfg)
        self.assertEqual(code, 1)
        self.assertIn("B1 는 버티컬별 항목이라 division", out)
        self.assertNotIn("A1 는", out)
        self.assertIn("business_lines", out)

    def test_same_company_in_two_units_is_merged_not_dropped(self):
        a = target("Omega", "https://omega.com", ["상", "상", "확인불가", "상", "상", "상", "상", "상"])
        b = target("Omega Corp", "https://www.omega.com", ["확인불가"] * 2 + ["중"] + ["확인불가"] * 5)
        b["business_lines"] = [{"vertical": "공장 보안", "division": "산업보안", "source": "https://omega.com/f"}]
        self.write("records/u1.json", {"unit": "u1", "companies": [a]})
        self.write("records/u2.json", {"unit": "u2", "companies": [b]})
        run("score", self.dir, "--config", self.cfg)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["B1"], "중(10)")              # u2 에서 보완
        self.assertEqual(rows[0]["total"], str(100 - 15 + 10))
        self.assertIn("공장 보안(미조사)", rows[0]["other_verticals"])

    def test_registry_one_proposal_per_company_across_verticals(self):
        self.write("records/u1.json", {"unit": "u1", "companies": [
            target("Alpha", "https://alpha.com", ["상"] * 8),
            target("Kappa", "https://kappa.com", ["중"] * 8, ko_hit="K1"),
        ]})
        run("score", self.dir, "--config", self.cfg)
        run2 = self.make_run("run2", "오피스")
        low = target("Alpha", "https://www.alpha.com", ["상", "상", "하", "상", "하", "하", "하", "중"])
        self.write("records/u1.json", {"unit": "u1", "companies": [
            low, target("Kappa", "https://kappa.com", ["상"] * 8), target("Beta", "https://beta.com", ["중"] * 8)]},
            run_dir=run2)
        run("score", run2, "--config", self.cfg)
        rows2 = {r["company"]: r for r in self.rows(run2)}
        self.assertEqual(rows2["Alpha"]["proposal_vertical"], "건설")
        self.assertIn("타버티컬제안", rows2["Alpha"]["review_flag"])
        self.assertIn("타버티컬KO", rows2["Kappa"]["review_flag"])
        self.assertIn("D2 회사공통 불일치", rows2["Alpha"]["review_flag"])
        with open(os.path.join(self.root, "_registry", "companies.csv"), encoding="utf-8-sig") as f:
            reg = {r["company"]: r for r in csv.DictReader(f)}
        self.assertEqual(len(reg), 3)                           # Alpha 는 한 줄
        self.assertEqual(reg["Alpha"]["proposal_vertical"], "건설")
        self.assertEqual(reg["Alpha"]["multi_vertical"], "Y")
        self.assertIn("오피스", reg["Alpha"]["other_verticals"])
        self.assertIn("K1", reg["Kappa"]["excluded"])
        self.assertEqual(reg["Kappa"]["proposal_vertical"], "")
        self.assertEqual(reg["Beta"]["proposal_vertical"], "오피스")
        with open(os.path.join(self.root, "_registry", "company_facts.json"), encoding="utf-8") as f:
            facts = json.load(f)
        self.assertEqual(sorted(facts["alpha.com"]["items"]), ["A1", "A2", "B2", "D2"])
        code, out = run("registry", self.root, "--config", self.cfg)
        self.assertEqual(code, 0, out)
        self.assertIn("제안 대상 2곳", out)


if __name__ == "__main__":
    unittest.main()
