# vertical-research 설정 (예시)

> 이 파일을 대상 폴더의 `.claude/vertical-research.config.md` 로 복사해 고쳐 쓴다.
> 아래 제품과 기준은 **가상 예시**다. 실제 제품 정보·평가 기준은 퍼블릭 저장소에 올리지 말 것.

## 제품 요약

**AcmeFace** — 영상에서 얼굴을 검출·추출·매칭하는 얼굴인식 엔진(가상).

- 형태: 기기 내장용 Edge SDK, 서버용 SDK(REST API), VMS 플러그인
- 강점: 1:N 대규모 검색, 위조 방지(PAD), 기존 CCTV 재사용
- 공급 방식: 엔진 OEM 공급 — 고객사 제품에 탑재되는 구조

자세한 사양은 `product_spec` 경로의 문서를 본다.

## 기계 판독 설정

```json vr-config
{
  "product_name": "AcmeFace",
  "product_spec": "../docs/product_spec.md",
  "output_dir": "research",
  "top_n": 20,
  "regions": ["Global"],
  "public_terms": ["face recognition", "access control", "time and attendance", "VMS", "visitor management"],
  "confidential": ["미공개 로드맵", "고객사 단가", "내부 성능 시험 원본"],
  "contact_roles": [
    ["Product Manager", "Head of Product"],
    ["Business Development Director", "Partnership Manager"],
    ["CTO", "Solution Architect"]
  ],
  "knockout": [
    {"id": "K1", "name": "직접 경쟁사", "rule": "자체 FR 엔진/SDK/API 를 제품으로 판매", "check": "홈페이지에 FR Engine/SDK/API 가 별도 제품으로 있는지"},
    {"id": "K2", "name": "단순 유통업체", "rule": "자체 제품 없이 타사 제품만 판매", "check": "제품 목록이 타사 브랜드 위주인지"},
    {"id": "K3", "name": "관련 사업 없음", "rule": "출입통제·보안·인증 관련 제품이 없음", "check": "AC, VMS, CCTV, Identity, Kiosk 제품 존재 여부"},
    {"id": "K4", "name": "활동 확인 불가", "rule": "현재 사업 운영 여부를 확인할 수 없음", "check": "최근 2년 내 뉴스·제품 업데이트 존재 여부"}
  ],
  "scoring": [
    {"id": "A1", "scope": "company", "area": "기업 규모", "name": "매출 규모", "max": 15, "levels": {"상": 15, "중": 10, "하": 5},
     "check": "연매출·상장 여부·투자 유치액", "guide": "상: 1,000억 이상 / 중: 200억~1,000억 / 하: 200억 미만"},
    {"id": "A2", "scope": "company", "area": "기업 규모", "name": "임직원 수", "max": 10, "levels": {"상": 10, "중": 6, "하": 2},
     "check": "LinkedIn·공시 인원", "guide": "상: 200명 이상 / 중: 50~199명 / 하: 50명 미만"},
    {"id": "B1", "scope": "vertical", "area": "제품 적합도", "name": "자체 플랫폼·HW", "max": 15, "levels": {"상": 15, "중": 10, "하": 0},
     "check": "엔진을 탑재할 자체 SW 플랫폼·단말기·게이트 보유", "guide": "상: 자체 라인업 명확 / 중: SI·커스터마이징 위주 / 하: 유통·재판매"},
    {"id": "B2", "scope": "company", "area": "제품 적합도", "name": "연동 개방성", "max": 15, "levels": {"상": 15, "중": 10, "하": 0},
     "check": "Partners·Integration 메뉴, 공개 API·SDK", "guide": "상: 연동 생태계 공식 공개 / 중: 연동 사례만 / 하: 폐쇄형"},
    {"id": "C1", "scope": "vertical", "area": "도메인 적합도", "name": "생체인식 경험·니즈", "max": 15, "levels": {"상": 15, "중": 10, "하": 5},
     "check": "얼굴인식·생체인식 기능 언급, 인증 수단 고도화", "guide": "상: 안면인식 도입·연동 중 / 중: 카드·QR·지문만 / 하: 인증과 무관"},
    {"id": "C2", "scope": "vertical", "area": "도메인 적합도", "name": "1:N·서버 구조", "max": 10, "levels": {"상": 10, "중": 6, "하": 2},
     "check": "대규모 사용자 중앙 관리, 다중 지점 동기화", "guide": "상: 중앙 서버 1:N 필수 / 중: 단말 1:1 위주 / 하: 스탠드얼론"},
    {"id": "D1", "scope": "vertical", "area": "시장 영향력", "name": "고객 레퍼런스", "max": 10, "levels": {"상": 10, "중": 6, "하": 2},
     "check": "공개 고객 로고·Case Study", "guide": "상: Tier-1 10개 이상 / 중: 3~9개 / 하: 거의 없음"},
    {"id": "D2", "scope": "company", "area": "시장 영향력", "name": "지역 전개", "max": 10, "levels": {"상": 10, "중": 6, "하": 2},
     "check": "해외 지사·파트너망, 국내 거점", "guide": "상: 글로벌 다국가 / 중: 특정 국가 1~3위 / 하: 로컬 한정"}
  ]
}
```

## 역할별 추가 지침 (선택)

### ROLE_PLANNER
(예: 국내 업체와 해외 업체를 다른 단위로 나눈다)

### ROLE_RESEARCHER
(예: 매출은 최근 회계연도 기준, 원화 환산은 하지 않는다)

### ROLE_WRITER
(예: 보고서 첫머리에 제안 우선순위 5곳을 따로 뽑는다)
