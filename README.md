# Project_maiReport 폴더 구조

2026-10-14에 화면정의서의 화면 구성을 기준으로 재편했다. 원본은 이 폴더 하나이고, 나머지(GitHub·공유 사이트·SharePoint)는 여기서 내보내는 사본이다.

```
docs/            기획 산출물. 화면 단위로 나눈다.
  00_공통/       IA · 기능정의서 · 서비스소개 · 데이터모델 · MRS · 데이터흐름도 · 알림정책 · 프로토타입 · 화면정의서 엑셀
  10_홈/         오늘의 질문·코칭·목표. 식이/ (SharePoint 원본 엑셀 4종 포함) · 실천기록_LIFE-001/ · 홈화면 · 목표분석
  20_생활분석/   세 지표 기획서 · 지표별분석 화면 · 지표해석 문장 · 전체건강데이터 12종 · 세지표 아키텍처
  30_검진진료/   검진요약 · AI검진요약 · 진료요약 · 또래등수/ (산식·검증·전달패키지) · 셀비체크업/
  40_AI인사이트/
  50_더보기/     내정보관리 · 결제/이용권 · 건강데이터연동 · 더보기 화면정의서
  _archive/      대체된 판. 지우지 않고 여기로 옮긴다.
data/            기준 데이터. 또래등수_참조표/ (raw/는 git 제외) · kosis_건강검진통계_2024/ · 지식DB/
reference/       외부에서 받은 자료. 계산식_전달문서_LJH/ · legal/ (git 제외) · 핸드오프_zip/
site/            공유 사이트 원본(source/)과 빌드 결과(build/), 배포 스크립트. 배포는 site/RSNA-DEPLOY.cmd
qa/              QA 실행기(bin·lib·plans·templates)와 결과(results/<기능>-<날짜>/)
scripts/         SharePoint 동기화
tools/           Figma 플러그인
```

## 규칙
- 파일 이름은 `..._v1.0.0.<확장자>`로 고정하고 버전은 파일 안에 적는다. 이름을 바꾸면 SharePoint 공유 주소가 끊긴다.
- 같은 파일을 두 폴더에 두지 않는다. 전달용 묶음(`docs/30_검진진료/또래등수/전달패키지/`)만 예외다.
- 새 문서는 해당 화면 폴더에 넣는다. 어느 화면인지 애매하면 `00_공통`.

## 내보내기
| 대상 | 원본 폴더 | 방법 |
|---|---|---|
| GitHub Project_maiReport | 전체(legal·raw 제외) | git push |
| 공유 사이트 (GitHub Pages) | `site/source/` | `site/RSNA-DEPLOY.cmd` |
| SharePoint | `docs/10_홈/식이/` 엑셀 4종 | `scripts/sync-to-sharepoint.ps1` |
