# vertical-research: 버티컬 업체 조사 멀티 에이전트 플러그인

산업 버티컬 하나를 주면 **경쟁사 분석, 타깃 업체 발굴, Knock-Out 필터링, 평가표 채점, 한국어 보고서**까지 이어서 만드는 Claude Code 플러그인이다.
B2B 제품(엔진·SDK·부품)을 탑재할 파트너사를 찾는 영업 리서치에 맞춰 설계했다.

조사를 쪼개 병렬로 돌리고 보고서 작성자를 따로 두는 구조는 Anthropic 의 `deep-research` 예제 스킬에서 가져왔다. 역할을 독립시키고 게이트를 스크립트로 판정하는 방식은 [iterate-solo](https://github.com/MMSS9402/iterate-solo) 를 따랐다.

## 파이프라인

```
/vertical-research:run "건설현장 출입통제" Global 40

P  planner        조사 단위 3~6개로 분해 (경쟁사 분석 + Target 발굴)
R  researcher × N 단위별 병렬 웹 조사 → 업체별 Knock-Out·등급·근거·출처
G1 gate.py        형식 게이트: 누락 항목·출처 없는 등급 0건
V  verifier × N   출처를 다시 열어 독립 검증 → 확인/수정/강등/제외
S  gate.py        Knock-Out 적용 → 합산 → 중복 병합 → 순위 → 검토 표시
W  writer         한국어 보고서 (점수는 못 바꿈)
K  ko-reviewer    한국어 심사 S1/S2/S3 (지적만, 고치지 않음)
G2 gate.py        Top N 누락 0 · S1 0 → 아니면 writer 재작성 (최대 2회)
```

| 역할 | 하는 일 | 못 하는 것 | 모델 |
|---|---|---|---|
| 드라이버 (메인 Claude) | 에이전트 호출, 게이트 판정 | 직접 조사·작성·점수 수정 | 세션 |
| planner | 조사 단위·질문·검색어·출처 설계 | 업체 조사, 파일 쓰기 | opus |
| researcher | 웹 조사, records/notes 작성 | 담당 밖 단위 조사, 추측 등급 | sonnet |
| verifier | 출처 재확인, 판정 교정 | researcher 노트 열람, 직접 수정 | opus |
| writer | 보고서 작성·재작성 | 새 사실 추가, 점수·순위 변경 | opus |
| ko-reviewer | 번역체·AI 상투어·비문 심사 | 글 수정, 사실 심사 | opus |

### 설계 원칙

1. **점수는 스크립트가 계산한다.** 에이전트는 항목별 등급(상/중/하/확인불가)과 근거 URL 만 낸다. 합산, Knock-Out, 중복 병합, 순위는 `scripts/gate.py` 가 맡는다.
2. **확인 못 한 것은 `확인불가`.** 0점 처리하고, 2개 이상이면 `근거부족` 표시를 붙여 사람이 보게 한다.
3. **자기 채점 금지.** 조사자와 검증자, 작성자와 심사자를 분리했다. verifier 는 조사 노트를 보지 않는다.
4. **사람이 볼 곳을 좁힌다.** `경계`(Top N 컷 ±5), `근거부족`, `미검증` 표시가 붙은 업체만 다시 보면 된다.

## 설치

### Claude Code (CLI · Claude 데스크탑의 Code 탭)

```
/plugin marketplace add MMSS9402/vertical-research
/plugin install vertical-research@vertical-research
```

데스크탑 앱의 Code 탭도 같은 Claude Code 이므로 같은 명령으로 설치한다. 업데이트:

```
/plugin marketplace update vertical-research
/plugin update vertical-research@vertical-research
```

**요구 사항**: Python 3.8 이상 (`python3` 또는 `python`), WebSearch·WebFetch 도구 사용 가능.

### Claude 데스크탑 채팅 · claude.ai (단일 에이전트판)

채팅 화면에는 서브에이전트가 없다. 같은 절차를 한 에이전트가 순서대로 수행하는 **lite 스킬**을 쓴다.

1. [`dist/vertical-research-lite.zip`](dist/vertical-research-lite.zip) 을 내려받는다.
2. Claude 데스크탑(또는 claude.ai) → **설정 → 기능(Capabilities) → Skills → 스킬 업로드**에서 zip 을 올린다. 코드 실행 기능이 켜져 있어야 `gate.py` 가 돈다.
3. 채팅에서 설정 파일을 올리고 "건설현장 출입통제 버티컬 업체 조사해줘"처럼 요청한다.

lite 판은 병렬 조사와 검증자 독립성이 없어서 플러그인판보다 느리고 덜 엄격하다. 메뉴 이름은 앱 버전에 따라 다를 수 있다.

## 사용법

```
/vertical-research:init                          # 폴더당 1회: 설정 파일 생성
/vertical-research:run "건설현장 출입통제"          # 설정 기본값으로 실행
/vertical-research:run "카지노 VIP 인식" APAC 30   # 지역·top_n 지정
```

### 설정 파일 `.claude/vertical-research.config.md`

[`examples/vertical-research.config.md`](examples/vertical-research.config.md) 를 복사해 쓴다. 사람이 읽는 제품 요약과 `json vr-config` 블록 하나로 이뤄진다.

| 키 | 의미 |
|---|---|
| `product_name`, `product_spec` | 제안할 제품 이름과 사양 문서 경로 |
| `top_n`, `regions`, `output_dir` | 최종 후보 수, 기본 지역, 결과 폴더 |
| `knockout` | 제외 기준 `{id, name, rule, check}` |
| `scoring` | 평가 항목 `{id, area, name, max, levels:{상,중,하}, check, guide}` |
| `contact_roles` | 접촉할 직책 우선순위 |
| `public_terms` / `confidential` | 검색어에 써도 되는 용어 / 절대 외부로 내보내면 안 되는 것 |

> ⚠️ 설정 파일과 제품 사양에는 사내 자료가 들어간다. **퍼블릭 저장소에 커밋하지 말 것.** 이 저장소의 `.gitignore` 도 그 파일을 제외한다.

### 결과물 (`research/<버티컬>-<날짜>/`)

| 파일 | 내용 |
|---|---|
| `report.md` | 한국어 보고서: 요약, 경쟁 구도, Main Player, Top N, 업체별 제안 포인트, 다시 볼 업체 |
| `candidates.csv` | 순위·점수·항목별 등급·검토 표시·제외 사유 (Excel 에서 바로 열림) |
| `evidence.md` | 업체별 항목 근거와 출처 표 |
| `plan.md`, `notes/`, `records/`, `verify/` | 중간 산출물 |
| `ko_review.json`, `run_log.md` | 한국어 심사 결과, 실행 기록 |

## 구조

```
.claude-plugin/plugin.json, marketplace.json
commands/run.md              드라이버
commands/init.md             설정 부트스트랩
agents/planner.md            계획
agents/researcher.md         조사
agents/verifier.md           검증
agents/writer.md             작성
agents/ko-reviewer.md        한국어 심사
skills/vr-protocol/SKILL.md  규약 단일 출처 (산출물 형식·게이트·보안)
scripts/gate.py              형식 검사·채점·게이트
scripts/build_desktop_skill.py  lite 스킬 zip 빌드
desktop/SKILL.md             lite 스킬 본문
examples/                    설정 예시 (가상 제품)
tests/test_gate.py           gate.py 테스트
```

## 개발

```
python -m unittest discover -s tests       # gate.py 테스트
python scripts/build_desktop_skill.py      # dist/vertical-research-lite.zip 재생성
```

에이전트·프로토콜을 고쳤으면 lite zip 도 다시 빌드해 커밋한다.

## 한계

- 웹에 공개된 정보만 다룬다. 비상장사 매출·임직원 수는 `확인불가` 가 많이 나온다.
- verifier 가 확인한 것은 **출처에 그렇게 적혀 있다**는 사실까지다. 출처 자체가 틀릴 수 있다.
- 최종 Top N 은 초안이다. 판단과 접촉 여부는 사람이 정한다.

## 라이선스

MIT
