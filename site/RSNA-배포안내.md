# RSNA 시연 사이트 배포

1. 공유 사이트의 「최종 프로토타입」 탭과 RSNA 시연 화면은 같은 파일입니다. 원본은 `docs/화면/90_기타/프로토타입/maiReport_prototype_v1.0.0.html` 하나만 수정합니다.
2. 이 대화에서 **배포!**라고 요청하면 에이전트가 배포합니다. 직접 실행하려면 `site/RSNA-DEPLOY.cmd`를 더블클릭합니다.
3. `DONE: The updated site is live.`가 표시되면 완료입니다. 사이트가 자동으로 열립니다.

처음 GitHub 로그인이 뜨면 `srleeinkorea` 계정으로 로그인합니다. 이후에는 Windows Git Credential Manager가 보관한 인증을 사용합니다. 토큰을 파일에 넣을 필요는 없습니다.

`build-rsna.ps1`이 최종 프로토타입을 그대로 `site/build/prototype.html`로 내보냅니다. 이 파일만 별도 배포 저장소의 `prototype.html`에 업로드합니다. 배포 저장소의 `index.html`은 문서함 메뉴 페이지라 건드리지 않습니다(2026-10-14). 프로젝트 전체나 원자료는 올리지 않습니다. 현재 시연 HTML의 이미지는 문서 안에 포함되어 있습니다. 향후 외부 이미지 파일을 연결하면 배포 스크립트에도 해당 파일을 추가해야 합니다.

GitHub Pages 배포 시간은 별도로 필요합니다. 스크립트가 실제 공개 HTML과 원본을 비교하여 반영 완료를 확인합니다. 업로드 후 확인 시간이 초과되면 GitHub Actions에서 배포 상태를 확인한 후 다시 실행하세요. 실패한 push도 다시 실행하여 재시도할 수 있습니다.

- [문서함 메뉴](https://srleeinkorea.github.io/maireport-rsna-demo-k7x9m2q8v4n6/) · [최종 프로토타입 바로가기](https://srleeinkorea.github.io/maireport-rsna-demo-k7x9m2q8v4n6/#prototype)
- [배포 상태](https://github.com/srleeinkorea/maireport-rsna-demo-k7x9m2q8v4n6/actions)

배포 작업용 저장소는 `.tmp_artifact/rsna-deploy`(프로젝트 루트)에 자동 생성됩니다. 이 폴더의 파일은 직접 수정하지 마세요.

## 구글 사이트에 붙일 때

`site/_archive/source/gpt_maiReport_RSNA_google_sites_embed.html`(옛 RSNA 시연 기준, 구버전)을 삽입 코드에 붙여넣습니다. 이 사본은 구글 사이트의 이중 틀에 맞춰 두었습니다.
