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
        "scores": {sid: ({"level": lv, "evidence": f"{sid} 근거", "source": f"https://x.com/{sid}"}
                         if lv != "확인불가" else {"level": lv, "evidence": "", "source": ""})
                   for sid, lv in zip(SCORING, levels)},
        "contact_roles": [{"role": "Head of Product", "source": "https://x.com/team"}],
    }


def run(*args):
    p = subprocess.run([sys.executable, GATE, *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


class GateTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for d in ("records", "verify"):
            os.makedirs(os.path.join(self.dir, d))
        # top_n 을 3 으로 줄인 설정
        with open(CONFIG, encoding="utf-8") as f:
            text = f.read().replace('"top_n": 20', '"top_n": 3')
        self.cfg = os.path.join(self.dir, "cfg.md")
        with open(self.cfg, "w", encoding="utf-8") as f:
            f.write(text)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, rel, data):
        with open(os.path.join(self.dir, rel), "w", encoding="utf-8") as f:
            if isinstance(data, str):
                f.write(data)
            else:
                json.dump(data, f, ensure_ascii=False)

    def rows(self):
        with open(os.path.join(self.dir, "candidates.csv"), encoding="utf-8-sig") as f:
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
        self.assertEqual(rows["Alpha"]["total"], str(100 - 15 - 8))
        self.assertEqual(rows["Alpha"]["A1"], "확인불가(0)")
        self.assertEqual(rows["Alpha"]["D1"], "하(2)")
        self.assertNotIn("미검증", rows["Alpha"]["review_flag"])
        self.assertIn("검증 제외", rows["Beta"]["excluded"])
        self.assertIn("K2", rows["Gamma"]["excluded"])
        # 순위 업체 2곳 < top_n 3 → 추가 조사 신호
        self.assertEqual(code, 1)
        self.assertIn("WARN", out)

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


if __name__ == "__main__":
    unittest.main()
