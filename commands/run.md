---
description: 버티컬 업체 조사 드라이버 — 계획(planner) → 병렬 조사(researcher) → 독립 검증(verifier) → 스크립트 채점 → 보고서(writer) → 한국어 심사(ko-reviewer)를 진행하고 게이트를 스크립트로 판정한다. 버티컬 하나 = 한 번 실행.
argument-hint: '"<버티컬/Application>" [지역] [top_n]'
---

당신(메인 Claude)이 **드라이버**다. 직접 조사하거나 보고서를 쓰지 않는다. 에이전트를 호출하고, 파일을 옮기고, 게이트를 Bash 로 판정한다. 컨텍스트를 아끼려고 에이전트 산출물 전문은 읽지 않는다 — 게이트 결과와 에이전트 최종 요약만 본다.

**인자**: $ARGUMENTS — 첫 인자(따옴표)가 버티컬. 이어서 지역(선택), 맨 끝이 정수면 top_n 덮어쓰기. 지역은 설정 `region_groups` 의 대륙 이름(예: `북미`, `남미`, 쉼표로 여럿)이나 국가명이다.

진행 상황은 할 일 목록 도구가 있으면 단계별로 갱신한다 ("조사 계획", "업체 조사", "검증", "채점", "보고서 작성", "한국어 심사").

## 0) 준비

1. 프로토콜 `${CLAUDE_PLUGIN_ROOT}/skills/vr-protocol/SKILL.md` 를 Read.
2. 설정 `.claude/vertical-research.config.md` 를 Read. 없으면 멈추고 `/vertical-research:init` 을 안내한다.
3. 파이썬 확인: `for c in python3 python py; do "$c" -c "import sys; assert sys.version_info >= (3, 8)" 2>/dev/null && { echo "$c"; break; }; done` 로 실제로 실행되는 파이썬을 찾는다 (Windows 의 Microsoft Store 가짜 `python3` 는 `command -v` 로는 잡히지만 실행되지 않는다). 아무것도 안 나오면 멈춘다. 셸 변수는 Bash 호출 사이에 유지되지 않으므로, 아래 게이트 명령의 `$PY`·`$GATE`·`$RUN`·`$CFG` 는 매번 실제 경로로 바꿔 쓴다 (`GATE` = `${CLAUDE_PLUGIN_ROOT}/scripts/gate.py`).
4. 버티컬 표기를 정한다. 명부는 이 표기로 버티컬을 구분하므로, 같은 버티컬의 이전 실행(`<output_dir>/*/run.json`)이 있으면 그 `vertical` 표기를 그대로 쓴다. 이어서 실행 폴더를 스크립트로 만든다:
   ```bash
   "$PY" "$GATE" new-run "<output_dir>" --vertical "<버티컬 표기>" --regions "<지역1>,<지역2>" --config "<설정 파일 경로>"
   ```
   지역이 `region_groups` 의 이름이면 `run.json` 의 `countries` 에 국가 코드 목록이 들어간다.
   출력된 경로가 `RUN` 이다. 폴더명은 버티컬 표기(한국어 그대로) + 날짜이고, 폴더명에 못 쓰는 문자와 공백은 `-` 로 바뀐다 (예: `건설·산업현장-출입통제-출역관리-20261021`). 이미 있으면 `-2`, `-3` 이 붙는다. 하위 `notes/ records/ verify/` 와 `run.json` 도 함께 만들어진다. 직접 폴더를 만들거나 이전 실행 폴더에 쓰지 않는다.
5. top_n 을 인자로 덮어쓰면 `RUN/config.override.md` 에 설정 파일을 복사하고 json 블록의 `top_n` 만 바꾼 뒤, 이후 `--config` 로 그 파일을 쓴다. 아니면 원래 설정 파일 경로를 쓴다. 이를 `CFG` 라 한다.
6. 모호함 확인: 버티컬 이름이 여러 뜻으로 읽히거나 지역이 결과를 크게 바꾸는데 인자에 없으면, **한 번만** 사용자에게 묻는다. 답이 없으면 설정 기본값으로 진행한다.

모든 에이전트 프롬프트에는 다음 **공통 머리말**을 넣는다:
```
플러그인 경로: ${CLAUDE_PLUGIN_ROOT}
프로토콜: ${CLAUDE_PLUGIN_ROOT}/skills/vr-protocol/SKILL.md
설정: <CFG 절대경로>
제품 사양: <설정의 product_spec 절대경로>
실행 폴더: <RUN 절대경로>
업체 명부: <output_dir 절대경로>/_registry/ (없으면 "없음")
조사 지역: <지역> (국가: <run.json 의 countries, 없으면 생략>)
```

## 1) P — planner

`Agent(subagent_type="vertical-research:planner", run_in_background=false)`. 프롬프트: 공통 머리말 + 버티컬 + 지역 + top_n.
반환된 계획 전문을 `RUN/plan.md` 로 Write. `## 조사 단위` 아래 `### <unit>` 이 3~6개인지, Target 단위 목표 업체 수 합계가 top_n×1.5 이상인지 확인한다. 아니면 이유를 붙여 1회 재호출. `[확인 필요]` 가 있으면 사용자에게 한 줄로 묻고 답을 plan.md 에 반영한다.

## 2) R — researcher (병렬)

plan.md 의 단위마다 `Agent(subagent_type="vertical-research:researcher", run_in_background=false)` 를 **한 응답 안에서 동시에** 호출한다. 프롬프트: 공통 머리말 + `담당 단위: <unit>` + plan.md 의 그 단위 블록 원문 + `## 단위 간 경계` 원문 + 저장 경로 `RUN/records/<unit>.json`, `RUN/notes/<unit>.md`.

## 3) G1 — 형식 게이트

```bash
"$PY" "$GATE" check-records "$RUN" --config "$CFG"
```
- PASS → 4단계. `WARN: 조사 지역 밖 target` 이 있으면 run_log.md 에 적고 마무리 보고에 넣는다 (실패로 다루지 않는다).
- FAIL → 오류 줄을 단위별로 나눠, 해당 단위 researcher 를 **새로** 호출해 "records 의 형식 오류만 고쳐라 (재조사 금지, 확인 못 하면 확인불가)" + 오류 줄 원문을 준다. 병렬로. 다시 G1. 2회 연속 같은 오류면 멈추고 보고.

## 4) V — verifier (병렬)

target 업체가 있는 records 파일마다 `Agent(subagent_type="vertical-research:verifier", run_in_background=false)` 를 동시에 호출. 프롬프트: 공통 머리말 + `담당: RUN/records/<unit>.json` + 저장 경로 `RUN/verify/<unit>.json`. **notes 경로는 주지 않는다** (독립 검증).
업체가 25곳을 넘는 단위는 업체 목록을 반으로 나눠 verifier 2개에 맡기고 `verify/<unit>.json`, `verify/<unit>-2.json` 으로 받은 뒤, 드라이버가 둘의 `companies` 를 합쳐 `verify/<unit>.json` 하나로 만든다 (`unit` 값은 같게).

## 5) S — 채점 (스크립트)

```bash
"$PY" "$GATE" score "$RUN" --config "$CFG"
```
- PASS → 6단계.
- `WARN: 순위 업체 … < top_n` → **추가 조사 1회만**: 부족한 수만큼 plan.md 에 단위 하나를 덧붙여(기존 단위와 겹치지 않는 축) researcher → G1 → verifier → score 를 다시 돈다. 그래도 부족하면 그대로 진행하고 보고서에 부족분을 적게 한다. **추가 조사는 이 한 번뿐이다.**

## 6) W — writer

먼저 `RUN/report.md` 가 없으면 자리표시 한 줄 `<!-- vr:report-placeholder -->` 만 담아 Write 한다. 하네스가 서브에이전트의 **새** 보고서 파일 쓰기는 막지만 기존 파일 Edit 는 허용하기 때문이다. 다른 버티컬 실행 뒤 명부가 바뀌어 기존 보고서를 **전면 재작성**할 때도, `RUN/_prev/` 에 기존 `report.md`·`ko_review.json` 을 옮겨 두고 `report.md` 를 자리표시 한 줄로 되돌린 뒤 writer 를 부른다 (Write 로 덮어쓰기도 막힌다).
`Agent(subagent_type="vertical-research:writer", run_in_background=false)`. 프롬프트: 공통 머리말 + 버티컬 + 저장 경로 `RUN/report.md`.
writer 응답에 `=====BEGIN report.md=====` 블록이 있으면 (하네스가 서브에이전트의 보고서 파일 쓰기를 막은 경우) 그 사이 본문을 고치지 말고 그대로 `RUN/report.md` 에 Write 한다. 재작성 회차도 같다.

## 7) K — ko-reviewer

`Agent(subagent_type="vertical-research:ko-reviewer", run_in_background=false)`. 프롬프트: 공통 머리말 + 심사 대상 `RUN/report.md` + 저장 경로 `RUN/ko_review.json`.

## 8) G2 — 보고서 게이트

```bash
"$PY" "$GATE" check-report "$RUN" --config "$CFG"; echo "REPORT=$?"
"$PY" "$GATE" check-ko "$RUN"; echo "KO=$?"
```
- 둘 다 0 → 9단계.
- check-ko 가 "quote 가 report.md 에 없음"으로만 실패 → ko-reviewer 를 새로 호출해 해당 지적의 quote 만 본문 그대로 다시 적게 한다 (회차로 세지 않음, 1회).
- 그 밖의 실패 → writer 를 새로 호출해 재작성: 공통 머리말 + "ko_review.json 의 S1 을 모두 반영, check-report 실패 줄: <원문>". 이어서 7) → 8). **재작성은 최대 2회.** 그래도 실패하면 남은 지적을 run_log.md 에 적고 9단계로 간다.

## 9) 마무리

1. `RUN/run_log.md` 에 단계별 결과(게이트 출력 한 줄씩, 재시도 횟수, 남은 지적)를 append.
2. 사용자에게 6줄 이내로 보고: 보고서 경로, 후보/제외/Top N 수, 검토 표시 업체 수, 다중 버티컬 업체 수와 명부 경로(`_registry/companies.csv`, 업체당 제안서 1건 기준 전체 제안 대상 수), 남은 S1(있으면), 다음에 사람이 볼 것. 보고서 전문을 채팅에 붙이지 않는다.

## 금지

- 드라이버가 직접 검색·조사·보고서 작성·점수 수정을 하지 않는다.
- 게이트를 건너뛰거나, 게이트 결과를 모델 판단으로 대체하지 않는다.
- 이전 실행 폴더를 덮어쓰지 않는다.
- 설정의 `confidential` 내용을 에이전트 프롬프트에 넣지 않는다 (설정 파일 경로만 준다).
