# maiReport 문서 보드 생성기 (Figma 플러그인)

화면정의서·기획서 HTML을 Figma **오토 레이아웃 프레임**으로 만들어 주는 개발용 플러그인입니다.
SVG로 넣었을 때처럼 좌표가 고정되지 않으므로, Figma 안에서 글을 고치면 표와 카드가 따라 늘어나고 카드 순서를 바꿔도 아래가 밀려 내려갑니다.

## 설치 (한 번만)
1. Figma **데스크톱 앱**을 엽니다(브라우저 버전은 개발 플러그인을 불러올 수 없습니다).
2. 메뉴 → Plugins → Development → **Import plugin from manifest…**
3. 이 폴더의 `manifest.json`을 선택합니다.

## 사용
1. 보드를 만들 Figma 파일을 열고, Plugins → Development → **maiReport 문서 보드 생성기** 실행
2. 창에 `Claude outputs/mai-report-*.html` 파일을 끌어다 놓습니다(또는 클릭해서 선택).
   - 예: `mai-report-생활지표_기획서_v1.0.0.html`, `mai-report-목표분석_화면정의서_v1.0.0.html`, `mai-report-지표별분석_화면정의서_v1.0.0.html`
3. 보드 폭(기본 1200px)을 정하고 **보드 생성**을 누릅니다. 표가 많은 문서는 수십 초 걸립니다.
4. `[문서] 제목` 이름의 프레임이 생기고 선택된 상태로 화면에 맞춰집니다.

같은 문서를 다시 넣으면 기존 `[문서] 제목` 프레임을 지우고 새로 만듭니다(옵션으로 끌 수 있음). Figma에서 직접 고친 내용은 재생성 시 사라지므로, 문서 원본(HTML)을 고친 뒤 재생성하는 흐름을 권합니다.

## 읽는 구조
우리 문서 HTML의 공통 구조를 그대로 읽습니다. 새 문서를 만들 때 이 구조를 지키면 별도 변환 없이 바로 들어갑니다.

| HTML | Figma |
|---|---|
| `.hero` (h1 · p · .meta) | 파란 히어로 카드 |
| `section.card` 또는 `div.card` + `h2`(번호 `.n`/`.num`) + `.sub` | 흰 장 카드 |
| `h3` · `p` · `ul/ol` | 소제목 · 문단 · 불릿 |
| `table` (th의 `style="width:…"`가 있으면 열 비율로 사용) | 행 단위 오토 레이아웃 표(헤더 회색 · 짝수 행 옅은 배경) |
| `.callout` (`.warn` · `.risk`) | 왼쪽 색 막대가 있는 안내 박스 |
| `.formula-box` | 짙은 배경 코드 블록(Roboto Mono) |
| `.grid2` / `.grid3` 안의 `.mini` / `.minicard` | 2열·3열 미니카드 |
| `.flow` | 가로 단계 카드 |
| `.tile` | 지표 타일 |
| `.sample` | 샘플 내용을 텍스트 안내 박스로 요약 |

JSON(`{title, subtitle, meta, sections:[{num,title,sub,blocks:[…]}]}`)도 그대로 넣을 수 있습니다.

## 폰트
Noto Sans KR → Pretendard → Inter 순으로 있는 폰트를 씁니다. 산식 블록은 Roboto Mono입니다. 모두 Figma 기본 Google Fonts에 있어 별도 설치가 필요 없습니다.

## 한계
- 화면 목업 SVG·이미지(예: 주간 그래프 예시, 육각 아이콘)는 그리지 않고 텍스트 안내로 대체합니다. 목업은 `mai-report-화면세트_figma용.zip`의 SVG를 따로 넣어 주세요.
- 문단 안의 굵게·링크 같은 인라인 서식은 평문으로 들어갑니다.
- 네트워크를 쓰지 않습니다(`networkAccess: none`). 문서 내용은 Figma 밖으로 나가지 않습니다.
