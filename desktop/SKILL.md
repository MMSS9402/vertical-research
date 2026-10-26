---
name: vertical-research-lite
description: 버티컬(산업·Application)별 경쟁사와 타깃 업체를 웹에서 조사해 Knock-Out 필터·평가표 채점·한국어 보고서까지 만든다. 서브에이전트가 없는 Claude 데스크탑·claude.ai 채팅용 단일 에이전트판. "건설현장 출입통제 버티컬 업체 조사해줘", "카지노 VIP 인식 타깃 업체 찾아줘" 같은 요청에 사용.
---

# vertical-research lite (단일 에이전트판)

Claude Code 플러그인 `vertical-research` 의 멀티 에이전트 파이프라인을 **한 에이전트가 역할을 바꿔 가며 순서대로** 수행한다. 산출물 형식과 게이트는 플러그인과 같다.

## 이 스킬 폴더의 파일

| 경로 | 용도 |
|---|---|
| `references/vr-protocol.md` | 산출물 형식·게이트·보안 규칙 (정본) |
| `references/planner.md` … `ko-reviewer.md` | 역할별 지침 |
| `references/config.example.md` | 설정 예시 (가상 제품) |
| `scripts/gate.py` | 형식 검사·채점·게이트 (표준 라이브러리만) |

역할 지침 안의 `${CLAUDE_PLUGIN_ROOT}` 는 이 스킬 폴더로 읽는다. 역할 지침의 "서브에이전트", "드라이버가 준다" 표현은 무시하고 아래 순서를 따른다.

## 시작 전

1. `references/vr-protocol.md` 를 읽는다.
2. **설정**: 사용자가 설정 파일(`vertical-research.config.md`)을 올렸으면 그것을, 없으면 제품 이름·사양 요약·평가 기준을 물어 `references/config.example.md` 형식으로 만든다. 사용자가 기준을 주지 않으면 예시 기준을 쓰고 보고서 첫머리에 그렇게 적는다.
3. 실행 폴더 `RUN` 을 작업 공간에 `python scripts/gate.py new-run <output_dir> --vertical "<버티컬>" --regions "<지역>" --config <설정 파일>` 으로 만든다 (지역이 설정 `region_groups` 의 대륙 이름이면 `run.json` 에 국가 목록이 들어간다. 폴더명은 버티컬 표기 + 날짜, 하위 `notes/ records/ verify/` 와 `run.json` 포함).
4. 코드 실행이 안 되는 환경이면 gate.py 대신 protocol §5 규칙을 직접 적용하고, 그 사실을 보고서에 적는다.

## 순서

각 단계 시작 때 해당 `references/<역할>.md` 를 읽고 그 역할로만 일한다.

1. **계획** (planner.md) — 조사 단위 3~5개. 데스크탑판은 도구 호출 한도가 작으므로 단위당 목표 업체 수를 줄이고 top_n 기본값은 20으로 둔다.
2. **조사** (researcher.md) — 단위를 하나씩 순서대로. 단위마다 records/notes 저장.
3. **형식 게이트** — `python scripts/gate.py check-records RUN --config CFG`. 실패 줄만 고친다.
4. **검증** (verifier.md) — 조사 때의 기억에 기대지 말고 출처 URL 을 **다시 열어** 확인한다. 특히 K1 직접 경쟁사와 배점 큰 항목. verify/<unit>.json 저장.
5. **채점** — `python scripts/gate.py score RUN --config CFG`. 점수는 스크립트 결과만 쓴다.
6. **작성** (writer.md) — report.md.
7. **한국어 심사** (ko-reviewer.md) — 방금 쓴 글이 아니라 남이 쓴 글이라고 보고 엄격하게 읽는다. ko_review.json 저장.
8. **보고서 게이트** — `check-report`, `check-ko`. S1 이 남으면 6→7→8 을 최대 2회 반복.

## 여러 버티컬 조사

한 SI 업체가 여러 버티컬 사업을 할 수 있다. 버티컬을 바꿔 다시 실행할 때 **같은 작업 폴더**(`output_dir`)를 쓰면 `score` 가 `_registry/` 명부를 갱신해 업체당 제안서 1건으로 묶는다. 새 채팅에서 이어 하려면 이전 실행 폴더를 다시 올려야 명부가 이어진다.

## 마무리

report.md, candidates.csv, evidence.md 를 사용자에게 파일로 건넨다. 채팅에는 5줄 요약만: Top N 수, 제외 수, 검토 표시 업체 수, 남은 S1, 사람이 다음에 볼 것.

## 보안

설정의 `confidential` 항목과 사내 사양 원문은 검색어에 넣지 않는다. 사내 자료를 이 채팅에 올려도 되는지는 회사 정책을 따른다.
