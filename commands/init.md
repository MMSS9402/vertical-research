---
description: vertical-research 설정 부트스트랩 — 현재 폴더에 .claude/vertical-research.config.md 를 만든다. 제품 사양 문서와 평가 기준을 사용자 자료에서 찾아 채우고, 찾지 못한 값은 TODO 로 남기고 묻는다. 폴더당 1회.
argument-hint: [제품 사양 문서 경로 — 선택]
---

당신(메인 Claude)이 **설정 부트스트래퍼**다. 원칙: **사용자 자료에서 확인한 값만 쓴다.** 확인하지 못한 값은 지어내지 말고 `TODO:` 로 두고 한 줄로 묻는다.

**인자**: $ARGUMENTS (제품 사양 문서 경로, 선택)

## 절차

1. `.claude/vertical-research.config.md` 가 이미 있으면 덮어쓰지 않는다. 무엇을 바꿀지 묻는다.
2. 템플릿 `${CLAUDE_PLUGIN_ROOT}/examples/vertical-research.config.md` 를 Read.
3. 자료 찾기 (현재 폴더 기준, Glob/Grep):
   - 제품 사양: 인자 경로 → `docs/**/*spec*`, `**/*사양*`, `**/*product*` 순으로 찾는다. PDF 만 있으면 텍스트를 뽑아 `docs/product_spec.md` 로 저장할지 묻는다.
   - 평가 기준: `Knock-Out`, `배점`, `평가`, `scoring` 이 들어간 md 를 찾는다. 찾으면 표를 `knockout`·`scoring` 형식으로 옮긴다 (id 는 원문 번호 유지, levels 점수는 원문 그대로).
   - 항목마다 `scope` 를 정한다. 회사 전체에 하나뿐인 값(매출, 임직원 수, 지역 전개, 연동 개방성 등)은 `company`, 사업부·버티컬마다 달라지는 값(자체 플랫폼, 도메인 경험, 아키텍처, 레퍼런스 등)은 `vertical`. 정한 결과를 표로 보여 주고 사용자 확인을 받는다.
   - 제안 담당자 직책: `담당자`, `Contact`, `Product Manager` 로 찾는다.
4. 템플릿의 가상 예시를 실제 값으로 바꿔 `.claude/vertical-research.config.md` 를 Write. 못 찾은 키는 `"TODO: ..."` 문자열로 둔다.
5. `public_terms` 와 `confidential` 은 반드시 사용자에게 확인한다 — 검색어로 써도 되는 공개 명칭과, 절대 외부로 나가면 안 되는 항목.
6. 검증: `PY=$(command -v python3 || command -v python)` 후 빈 임시 폴더를 만들어 `"$PY" "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py" check-records <임시폴더> --config .claude/vertical-research.config.md` 를 실행한다. "records 없음" 오류는 정상이다 (설정 파싱이 통과했다는 뜻). `ERROR:` 로 시작하는 설정 오류가 나오면 고친다.
7. 사용자에게 보고: 채운 값, 남은 TODO, 실행 예시 `/vertical-research:run "건설현장 출입통제" Global 40`.

## 주의

- 이 설정 파일에는 사내 자료가 들어갈 수 있다. 퍼블릭 저장소에 올리지 말라고 안내하고, 폴더가 git 저장소면 `.gitignore` 에 `.claude/vertical-research.config.md` 를 추가할지 묻는다.
