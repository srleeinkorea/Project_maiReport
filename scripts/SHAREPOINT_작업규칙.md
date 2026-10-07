# SharePoint 엑셀 4종 작업 규칙 (충돌 방지)

대상: 식이 데이터계약 · 참조설정데이터 · 의학검수 · 근거대조

## 원칙
1. 정본은 내 컴퓨터 `outputs/mai-report-policy/식이/`의 파일이다. SharePoint는 보여 주는 사본이다.
2. 한 번에 한 쪽에서만 고친다. 크롬 클로드가 SharePoint에서 고치는 동안에는 로컬 정본을 고치지 않고, 로컬에서 고치는 동안에는 크롬 클로드가 SharePoint 파일을 열지 않는다.
3. 크롬 클로드가 바꾸고 싶은 내용은 파일에 직접 쓰지 않고 "바꿀 칸 · 전 · 후"를 적어 전달한다. 로컬에서 반영한 뒤 스크립트로 올린다.

## 올리는 순서 (로컬 → SharePoint)
1. `powershell -ExecutionPolicy Bypass -File scripts\sync-to-sharepoint.ps1`
2. "보류"가 뜨면 사이트에서 누가 고친 것이다. 사이트 파일을 열어 달라진 내용을 로컬에 먼저 합친 뒤 `-Force`로 올린다.
3. 덮어쓰기 직전의 사이트 파일은 `scripts\.sp-backup\날짜-시각\`에 자동으로 남는다.
4. 올린 뒤 웹에서 확인할 때는 Ctrl+F5로 새로고침한다.

## 크롬 클로드에게 줄 지시문
> 식이 엑셀 4종은 SharePoint에서 직접 수정하거나 저장하지 않는다. 바꿀 내용은 시트·행·전·후로 정리해서 이사라에게 전달한다. 다운로드 폴더의 "(1)" 복사본을 다시 올리려 하지 않는다.

## 자동 동기화 (가장 최신 파일을 자동으로 올리기)
- 스크립트: `scripts\auto-sync-sharepoint.ps1`
- 한 번만: `powershell -ExecutionPolicy Bypass -File scripts\auto-sync-sharepoint.ps1 -Once`
- 계속 지켜보기: `... -Watch` (기본 60초마다 확인, Ctrl+C로 끝)
- 미리 보기: `-DryRun` (올릴 파일만 로그로 보여 주고 올리지는 않음)
- 올리지 않는 경우: 파일이 깨졌거나, 시트 수가 줄었거나, 엑셀이 열어 둔 파일이거나, 아직 저장 중인 파일.
- 사이트에서 누가 고친 흔적(마지막에 올린 문장과 다름)이 있으면 `scripts\.sp-backup\`에 백업하고 로그(`scripts\auto-sync.log`)에 남긴 뒤 덮어쓴다.
- 이 자동화는 OneDrive 폴더까지만 맞춘다. 클라우드로 실제로 올라갔는지는 OneDrive 구름 아이콘으로 확인한다. 「보류 중」에서 멈추면 사이트 폴더에 직접 올린다.
