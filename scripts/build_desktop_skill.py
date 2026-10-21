#!/usr/bin/env python3
"""Claude 데스크탑·claude.ai 업로드용 스킬 zip 을 만든다.

Usage: python scripts/build_desktop_skill.py   → dist/vertical-research-lite.zip
"""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "vertical-research-lite"
FILES = {
    "SKILL.md": "desktop/SKILL.md",
    "references/vr-protocol.md": "skills/vr-protocol/SKILL.md",
    "references/planner.md": "agents/planner.md",
    "references/researcher.md": "agents/researcher.md",
    "references/verifier.md": "agents/verifier.md",
    "references/writer.md": "agents/writer.md",
    "references/ko-reviewer.md": "agents/ko-reviewer.md",
    "references/config.example.md": "examples/vertical-research.config.md",
    "scripts/gate.py": "scripts/gate.py",
}


def main():
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", f"{NAME}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dst, src in FILES.items():
            z.write(os.path.join(ROOT, src), f"{NAME}/{dst}")
    print(out)


if __name__ == "__main__":
    main()
