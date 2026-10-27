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
  "region_groups": {
    "북미": ["US", "CA", "MX"],
    "남미": ["AR", "BO", "BR", "CL", "CO", "EC", "GY", "PE", "PY", "SR", "UY", "VE"]
  },
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
    {"id": "K4", "name": "활동 확인 불가", "rule": "현재 사업 운영 여부를 확인할 수 없음", "check": "최근 2년 내 뉴스·제품 업데이트 존재 여부"},
    {"id": "K5", "name": "SDK 개발 주체 아님", "rule": "엔진 SDK 를 받아 자기 제품·솔루션에 넣어 개발하는 사업이 없음. 본업이 통신·유통·금융·숙박 같은 서비스 운영이고 솔루션은 사서 쓰는 최종 이용 기업", "check": "자체 개발한 SW·HW 제품을 외부 고객에게 팔거나 SI·솔루션 구축 사업을 하는지. 사내 개발팀이 자사 서비스만 만들면 해당"},
    {"id": "K6", "name": "자체 Matching 엔진 보유", "rule": "얼굴 Matching(1:1 인증·1:N 식별)까지 하는 자체 개발 엔진을 자기 제품에 씀. 얼굴 Detection 만 자체 보유하면 해당 안 됨", "check": "홈페이지·데이터시트·백서에 자체 개발(proprietary, in-house) 얼굴인식 알고리즘, NIST FRTE(FRVT) 참가, 얼굴인식 특허가 있는지. 'powered by <타사 엔진>'·엔진사 파트너 발표로 타사 엔진 탑재가 확인되면 해당 안 됨"},
    {"id": "K7", "name": "FR 제품·기능 없음", "rule": "얼굴인식 제품이나 기능을 실제로 제공하지 않음. 객체 검출·번호판·행동 분석 같은 AI·Vision 일반만 하는 업체도 해당", "check": "제품 페이지·데이터시트에 Face Recognition·Face Verification·얼굴 인증 기능이 명시돼 있는지 (타사 엔진 연동으로 제공해도 기능이 있으면 해당 안 됨)"},
    {"id": "K8", "name": "외부 엔진 탑재 제품 없음", "rule": "외부 FR 엔진을 탑재·구동할 자체 HW 제품이 없음. VMS·보안 SW·SaaS 만 하는 업체가 해당", "check": "IP·AI 카메라(앱 플랫폼), AI Box·엣지 분석 장비, 출입 단말기, 키오스크, 게이트를 직접 개발해 파는지. 자사 VMS 만 돌리는 녹화 서버·NVR, 펌웨어를 직접 못 고치는 OEM 리브랜딩 장비는 해당 제품으로 치지 않음"}
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
