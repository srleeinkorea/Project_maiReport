# RSNA 시연 사이트 배포

1. 기존 버전은 `outputs/mai-report-rsna-demo/maiReport_RSNA시연_급성폐렴_프로토타입_v1.0.0.html`, GPT 버전은 같은 폴더의 `gpt_maiReport_RSNA_home_information_v1.0.0.html`을 수정합니다.
2. 이 대화에서 **배포!**라고 요청하면 에이전트가 배포합니다. 직접 실행하려면 프로젝트 폴더의 `RSNA-DEPLOY.cmd`를 더블클릭합니다.
3. `DONE: The updated site is live.`가 표시되면 완료입니다. 사이트가 자동으로 열립니다.

처음 GitHub 로그인이 뜨면 `srleeinkorea` 계정으로 로그인합니다. 이후에는 Windows Git Credential Manager가 보관한 인증을 사용합니다. 토큰을 파일에 넣을 필요는 없습니다.

`build-rsna.ps1`이 `version-tabs.html`에 두 버전의 HTML을 포함해 `outputs/rsna-github-upload/index.html`을 생성합니다. 이 통합본만 별도 배포 저장소에 업로드합니다. 두 화면은 독립적인 iframe에서 실행되며 탭 전환 시 진행 상태를 유지합니다. 주소 끝에 `#original` 또는 `#gpt`를 붙이면 원하는 버전으로 바로 열립니다. 프로젝트 전체나 원자료는 올리지 않습니다. 현재 시연 HTML의 이미지는 문서 안에 포함되어 있습니다. 향후 외부 이미지 파일을 연결하면 배포 스크립트에도 해당 파일을 추가해야 합니다.

GitHub Pages 배포 시간은 별도로 필요합니다. 스크립트가 실제 공개 HTML과 원본을 비교하여 반영 완료를 확인합니다. 업로드 후 확인 시간이 초과되면 GitHub Actions에서 배포 상태를 확인한 후 다시 실행하세요. 실패한 push도 다시 실행하여 재시도할 수 있습니다.

- [시연 사이트](https://srleeinkorea.github.io/maireport-rsna-demo-k7x9m2q8v4n6/)
- [배포 상태](https://github.com/srleeinkorea/maireport-rsna-demo-k7x9m2q8v4n6/actions)

배포 작업용 저장소는 `.tmp_artifact/rsna-deploy`에 자동 생성됩니다. 이 폴더의 파일은 직접 수정하지 마세요.
