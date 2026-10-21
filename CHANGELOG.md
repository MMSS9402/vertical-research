# Changelog

## 0.2.0

여러 버티컬 사업을 하는 업체(SI 등)를 제대로 다루도록 바꿨습니다.

- **업체 1곳 = 제안서 1건.** 실행 간 업체 명부 `<output_dir>/_registry/`(companies.csv, summary.md, company_facts.json)를 추가했습니다. 점수가 가장 높은 버티컬이 제안 버티컬이 됩니다.
- 평가 항목에 `scope`(`company`/`vertical`)를 추가했습니다. 회사 공통 값은 명부에서 다시 씁니다.
- 버티컬 항목 근거에 `division`(근거 사업부)이 필수가 됐습니다. verifier 가 다른 사업부 근거를 강등합니다.
- records 에 `business_lines`(다른 버티컬 사업 영역)를 추가했습니다.
- 같은 실행 안에서 같은 업체가 두 번 나오면 한쪽을 버리지 않고 합칩니다.
- 새 검토 표시: `타버티컬제안`, `타버티컬KO`, `<id> 회사공통 불일치`.
- `gate.py registry` 명령 추가. 실행 폴더에 `run.json`, `scored.json` 추가.
- README 를 누구나 읽기 쉽게 다시 썼습니다.
- 수정: `commands/run.md` 의 frontmatter YAML 오류로 명령 설명·인자 힌트가 표시되지 않던 문제.

**설정 파일 영향**: 기존 설정은 그대로 동작합니다(`scope` 가 없으면 `vertical`). 회사 공통 항목에 `"scope": "company"` 를 추가하면 재사용과 불일치 검사가 켜집니다.

## 0.1.0

- 첫 공개. planner · researcher · verifier · writer · ko-reviewer 5개 에이전트와 드라이버(`/vertical-research:run`), 설정 부트스트랩(`/vertical-research:init`).
- `scripts/gate.py`: check-records · score · check-report · check-ko.
- Claude 데스크탑 채팅용 단일 에이전트판 `dist/vertical-research-lite.zip`.
