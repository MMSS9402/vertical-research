---
name: vr-protocol
description: vertical-research 멀티 에이전트 파이프라인(계획→조사→검증→채점→작성→한국어 심사)의 규약 단일 출처(SSOT). 드라이버(run.md)와 planner·researcher·verifier·writer·ko-reviewer 가 따르는 산출물 형식·게이트·보안 규칙. 제품 정보와 평가 기준은 사용자 폴더의 .claude/vertical-research.config.md 가 정의한다.
---

# vertical-research 프로토콜 (SSOT)

이 문서가 파이프라인의 규약 정본이다. 에이전트 정의나 명령 문서와 충돌하면 이 문서가 이긴다.

## 1. 파이프라인

```
P  planner      → plan.md                         (조사 단위 분해)
R  researcher×N → notes/<unit>.md, records/<unit>.json   (병렬)
G1 gate.py check-records                          (형식·출처 게이트)
V  verifier×N   → verify/<unit>.json              (병렬, 독립 검증)
S  gate.py score → candidates.csv, evidence.md    (Knock-Out·채점·순위: 스크립트)
                  → <output_dir>/_registry/       (실행 간 업체 명부 갱신)
W  writer       → report.md
K  ko-reviewer  → ko_review.json
G2 gate.py check-report, check-ko                 (S1 0건 · Top N 누락 0건)
   └ fail → writer 재작성 (최대 2회) → K → G2
```

- 각 에이전트는 **앞 단계 산출물만** 받는다. 다른 에이전트의 추론 과정은 전달하지 않는다.
- 판정은 모델 감이 아니라 `scripts/gate.py` 의 종료 코드로 한다.
- **점수는 스크립트만 계산한다.** 에이전트는 항목별 등급(상/중/하/확인불가)과 근거만 낸다. writer 는 점수를 바꾸지 못한다.
- **업체 1곳 = 제안서 1건.** 한 SI 업체가 여러 버티컬 사업을 할 수 있다. 버티컬마다 따로 조사하되, 명부에서 업체 하나로 묶고 점수가 가장 높은 버티컬을 **제안 버티컬**로 정한다. 나머지 버티컬은 그 제안서의 확장 제안으로 들어간다.

## 1-1. 다중 버티컬 업체 규칙

| 구분 | 규칙 |
|---|---|
| 평가 항목 범위 | 설정의 각 항목에 `scope` 를 둔다. `company` = 회사 공통(매출, 임직원, 연동 개방성, 지역 등), `vertical` = 버티컬마다 다름(자체 플랫폼, 도메인 경험, 1:N 구조, 레퍼런스 등) |
| 근거 사업부 | `vertical` 항목은 근거가 **이번 버티컬을 맡는 사업부·제품군**의 것이어야 한다. `division` 에 그 이름을 적는다 (사업부가 하나뿐이면 `전사`). 다른 사업부 근거는 쓰지 않는다 |
| 다른 사업 영역 | researcher 는 업체가 하는 **다른 버티컬 사업**을 `business_lines` 에 출처와 함께 적는다 |
| 회사 공통 값 재사용 | 이전 실행에서 확인된 `company` 항목은 `_registry/company_facts.json` 에 있다. researcher 는 그 값을 옮겨 쓰고(`reused_from` 표시) 시간은 버티컬 항목에 쓴다 |
| Knock-Out | 회사 단위다. 한 버티컬 실행에서 걸리면 명부 전체에서 제외되고, 다른 실행의 같은 업체에는 `타버티컬KO` 가 붙는다. 다른 사업부가 FR 엔진·솔루션을 팔면 그 회사는 직접 경쟁사다 |
| 같은 실행 안 중복 | 두 단위가 같은 업체를 찾으면 버리지 않고 합친다. 한쪽의 `확인불가` 를 다른 쪽 근거로 채운다 |

## 2. 실행 폴더

`<output_dir>/<vertical-slug>-<YYYYMMDD>/` (output_dir 은 설정 파일 값, 기본 `research`)

```
plan.md
notes/<unit>.md
records/<unit>.json
verify/<unit>.json
run.json              # 드라이버: {"vertical": "...", "regions": [...], "date": "YYYY-MM-DD"}
scored.json           # 스크립트 생성 (명부 입력)
candidates.csv        # 스크립트 생성
evidence.md           # 스크립트 생성
report.md
ko_review.json
run_log.md            # 드라이버가 단계별 결과를 append
```

`<unit>` 은 영문 소문자·숫자·하이픈만 쓴다 (예: `main-players-kr`).

실행 간 공유 명부 `<output_dir>/_registry/` (score 가 매번 다시 만든다, 직접 수정 금지):

| 파일 | 내용 |
|---|---|
| `companies.csv` | 업체 1곳 = 1행. 제안 버티컬, 제안 점수, 함께 제안할 버티컬, 미조사 사업 영역, 제외 여부 |
| `company_facts.json` | 업체별 회사 공통 항목의 확인된 값 (재사용용) |
| `summary.md` | 전체·제안 대상·다중 버티컬 업체 수와 목록 |

같은 버티컬을 다시 돌리면 명부는 그 버티컬의 가장 최근 실행만 쓴다.

## 3. 설정 파일

사용자 폴더의 `.claude/vertical-research.config.md`. 사람이 읽는 제품 요약과, 스크립트가 읽는 ```` ```json vr-config ```` 블록 하나로 이뤄진다. 형식은 플러그인의 `examples/vertical-research.config.md` 를 따른다.

| 키 | 의미 |
|---|---|
| `product_name` | 제안할 우리 제품 이름 (공개 명칭) |
| `product_spec` | 제품 사양 문서 경로 (설정 파일 기준 상대경로 가능) |
| `output_dir` | 실행 폴더 상위 경로 |
| `top_n` | 최종 후보 수 |
| `regions` | 기본 조사 지역 |
| `knockout` | 제외 기준 목록 `{id, name, rule, check}` |
| `scoring` | 평가 항목 목록 `{id, scope, area, name, max, levels:{상,중,하}, check, guide}`. `scope` 는 `company`/`vertical` (생략 시 `vertical`) |
| `contact_roles` | 제안 담당자 직책 우선순위 |
| `public_terms` | 웹 검색어에 써도 되는 공개 용어 |
| `confidential` | 웹 검색어·외부 입력에 절대 쓰면 안 되는 내용 |

## 4. 산출물 형식

### 4-1. plan.md (planner)

```markdown
# 조사 계획: <버티컬>

## 범위
- 버티컬 / Application: ...
- 지역: ...
- 가정: (사용자가 정하지 않아 기본값을 쓴 것)

## 조사 단위
### <unit>
- 목적: ...
- 핵심 질문: ...
- 검색어 후보: (공개 용어만)
- 우선 출처: ...
- 산출: notes/<unit>.md, records/<unit>.json
- 목표 업체 수: <정수> (경쟁사 분석 단위는 0)

## 단위 간 경계
(중복 조사를 막는 규칙. 예: 국내 업체는 kr 단위만 다룬다)
```

조사 단위는 3~6개, 서로 겹치지 않게 나눈다. 최소 1개는 **경쟁사 분석** 단위, 나머지는 **Target 발굴** 단위다. Target 단위의 목표 업체 수 합계는 `top_n × 1.5` 이상이어야 Knock-Out 후에도 Top N 이 채워진다.

### 4-2. records/<unit>.json (researcher)

```json
{
  "unit": "main-players-kr",
  "companies": [
    {
      "company": "Example Corp",
      "homepage": "https://example.com",
      "country": "KR",
      "segment": "target",
      "summary": "건설현장 근태 SaaS. 자체 단말기와 모바일 앱 보유",
      "knockout": {
        "K1": {"hit": false, "evidence": "FR 엔진·SDK 판매 페이지 없음", "source": "https://example.com/products"}
      },
      "scores": {
        "A1": {"level": "중", "evidence": "2025년 매출 약 320억 원", "source": "https://..."},
        "A2": {"level": "확인불가", "evidence": "", "source": ""},
        "B1": {"level": "상", "evidence": "현장 근태 단말기 3종 자체 생산", "source": "https://...", "division": "건설솔루션사업부"}
      },
      "business_lines": [
        {"vertical": "스마트빌딩 출입통제", "division": "빌딩솔루션사업부", "source": "https://..."}
      ],
      "contact_roles": [{"role": "Head of Product", "source": "https://..."}]
    }
  ]
}
```

- `segment`: `target` (채점 대상) 또는 `competitor` (경쟁사, 채점 안 함).
- `target` 은 설정의 **모든** knockout id 와 **모든** scoring id 를 채운다.
- `level` 은 `상`·`중`·`하`·`확인불가` 중 하나. `확인불가` 가 아니면 `evidence` 와 `source`(http/https URL) 가 반드시 있다.
- `scope: vertical` 항목은 `확인불가` 가 아니면 `division` 도 반드시 있다.
- `business_lines` 는 이번 버티컬 **밖의** 사업 영역만 적는다. 항목마다 `vertical` 과 `source` 가 필요하다.
- 명부에서 옮겨 쓴 회사 공통 값에는 `"reused_from": "<실행 폴더명>"` 을 붙인다.
- `evidence` 는 출처에 적힌 사실을 짧게 옮긴다. 추정이면 "추정:"으로 시작하고 등급은 `확인불가` 로 둔다.
- `contact_roles` 에는 **직책만** 적는다. 개인 이름·개인 이메일·전화번호는 수집하지 않는다.

### 4-3. notes/<unit>.md (researcher)

자유 서술 노트. 경쟁사 단위는 업체별로 제품, 주력 버티컬, 강점, 약점, 우리 제품 대비 차별화 포인트를 출처와 함께 적는다. Target 단위는 records 에 담기지 않는 맥락(시장 구조, 파생 관계, 탈락시킨 업체와 이유)을 적는다.

### 4-4. verify/<unit>.json (verifier)

```json
{
  "unit": "main-players-kr",
  "companies": [
    {
      "company": "Example Corp",
      "status": "ok",
      "reason": "",
      "knockout": {"K1": {"hit": true, "evidence": "Face SDK 제품 페이지 존재", "source": "https://..."}},
      "items": {
        "A1": {"verdict": "confirmed"},
        "D1": {"verdict": "corrected", "level": "하", "evidence": "공개 사례 2건", "source": "https://..."},
        "B2": {"verdict": "unsupported", "reason": "출처 페이지에 API 언급 없음"}
      }
    }
  ]
}
```

- `status`: `ok` (유지) · `fix` (일부 수정) · `drop` (실존 확인 불가·중복·범위 밖 → 제외).
- `items.*.verdict`: `confirmed` · `corrected` (level/evidence/source 교체) · `unsupported` (확인불가로 강등).
- `summary` (선택): 검증으로 records 의 `summary` 내용이 틀리게 됐을 때(예: "얼굴인식 언급 없음"인데 홈페이지에 있음) 고친 한 줄 요약을 적는다. 스크립트가 candidates.csv 의 요약을 이것으로 바꾼다.
- `homepage` (선택): records 의 홈페이지가 비었거나 틀렸을 때만 공식 홈페이지 URL 을 적는다. 스크립트가 records 값을 이것으로 바꾸고, 같은 업체 병합도 이 값으로 한다.
- `knockout` 에는 판정을 **바꾸는** 항목만 적는다.
- records 에 있는 업체는 빠짐없이 한 번씩 다룬다.

### 4-5. ko_review.json (ko-reviewer)

```json
{
  "findings": [
    {"severity": "S1", "quote": "report.md 에서 그대로 복사한 구절", "issue": "번역체", "fix": "고친 문장 제안"}
  ],
  "summary": "전체 평"
}
```

- `quote` 는 report.md 에 **글자 그대로** 있어야 한다 (스크립트가 확인).
- 심각도 기준은 `agents/ko-reviewer.md` 에 있다.

## 5. 게이트 (scripts/gate.py)

| 명령 | 통과 조건 |
|---|---|
| `check-records` | 모든 records JSON 이 4-2 형식을 지킴. 누락된 knockout/scoring id 0건, 출처 없는 등급 0건, 사업부 없는 버티컬 항목 0건 |
| `score` | (항상 실행) verify 반영 → 같은 업체 병합 → Knock-Out → 합산 → 정렬 → 명부 갱신. 형식 오류가 있으면 실패 |
| `registry` | 명부만 다시 만든다 (`<output_dir>` 를 인자로) |
| `check-report` | report.md 존재, candidates.csv 의 Top N 업체명이 모두 본문에 등장 |
| `check-ko` | ko_review.json 형식 정상, quote 가 모두 report.md 에 존재, S1 0건 |

채점 규칙(스크립트 구현):
- Knock-Out 하나라도 `hit: true` → 제외.
- `확인불가` = 0점, `unknown_count` 로 집계.
- 같은 업체 판별은 홈페이지 도메인(`www.` 제외, 없으면 정규화한 업체명)으로 한다. 같은 실행 안에서는 `확인불가` 가 적은 기록을 바탕으로, 비어 있는 항목을 다른 기록으로 채운다.
- 명부의 제안 버티컬 = Knock-Out 이 없는 실행 중 합계가 가장 높은 버티컬.
- `review_flag`:

| 표시 | 뜻 |
|---|---|
| `근거부족` | `확인불가` 2개 이상 |
| `경계` | 순위가 `top_n` 경계 ±5 안 |
| `미검증` | verifier 가 다루지 않은 업체 |
| `타버티컬제안` | 이 업체의 제안서는 다른 버티컬 보고서 기준으로 1건만 쓴다 |
| `타버티컬KO` | 다른 버티컬 실행에서 Knock-Out 에 걸림 (명부에서 제외) |
| `<id> 회사공통 불일치` | 회사 공통 항목 등급이 실행마다 다름 — 사람이 확인 |

## 6. 보안 규칙 (모든 에이전트)

1. 웹 검색어·외부 요청에는 설정의 `public_terms` 와 일반 산업 용어만 쓴다. `confidential` 항목, 미공개 사양, 고객사 내부 정보는 절대 넣지 않는다.
2. 제품 사양 문서는 로컬에서 읽기만 한다. 원문을 외부로 보내지 않는다.
3. 개인 정보(이름·연락처)는 수집하지 않는다. 직책과 공개 페이지 URL 까지만.
4. 모든 사실에는 출처 URL 을 단다. 출처 없는 사실은 "확인불가".

## 7. 중단 조건

- 같은 게이트가 2회 연속 같은 이유로 실패하면 멈추고 사용자에게 보고한다.
- writer 재작성은 최대 2회. 그래도 S1 이 남으면 남은 지적을 run_log.md 에 적고 사람 검토로 넘긴다.
