# 폐렴 의심 영역이 작은 흉부 X-ray DICOM 후보 3건

이 자료는 **경증 폐렴으로 확정된 사례가 아닙니다.** RSNA 공식 공개 데이터의 최종 Calculated / Lung Opacity 주석이 1개인 영상 중, 주석 사각형 면적이 작은 PA 촬영 사례를 추린 참고 후보입니다. 임상 중증도, 확정 폐렴 진단, 원인균 정보는 확인되지 않았습니다. 작은 사각형은 경증의 근거가 아니며 실제 병변의 분할 면적도 아닙니다.

## 파일

|파일|촬영|해상도|주석 사각형 / 전체 영상 면적|
|---|---|---|---|
|candidate_01.dcm|PA|1024 × 1024|약 1.051%|
|candidate_02.dcm|PA|1024 × 1024|약 1.056%|
|candidate_03.dcm|PA|1024 × 1024|약 1.059%|

- `.dcm`: RSNA 배포 ZIP에서 추출한 바이트 그대로 보존한 파일.
- `.png`: DICOM을 디코딩한 미리보기.
- `_annotated.png`: 제공된 주석 사각형을 노란색으로 표시한 미리보기. DICOM 자체에는 표시를 추가하지 않았습니다.
- `selected_annotations.json`: 원본 주석, ZIP 내부 경로, SHA-256, 선택 기준.
- 세 파일 모두 pydicom으로 읽고 1024 × 1024 픽셀 배열 디코딩을 확인했습니다.
- 선택 절차: Calculated Lung Opacity 주석이 하나인 영상 중 사각형 면적이 전체 영상의 1% 이상인 사례를 면적 오름차순으로 검토하고, PA 촬영 3건을 선택했습니다. 이는 편의상 정한 검색 기준이며 검증된 중증도 기준이 아닙니다.

## 데이터 형식의 한계

RSNA는 NIH의 PNG 영상을 DICOM으로 변환하고 연령·성별·촬영방향 등의 태그를 추가했습니다. 따라서 이 파일은 유효한 배포 DICOM이지만 촬영 장비에서 나온 원본 DICOM은 아닙니다. 임상 판독이나 '경증 폐렴' 정답 데이터로 사용하려면 별도 전문의 검토 및 임상 정보가 필요합니다.

## 출처와 이용 조건

데이터 제공: **NIH Clinical Center**. 폐렴 의심 소견 주석 및 DICOM 배포: **RSNA / Society of Thoracic Radiology (STR)**.

- NIH 원본 데이터: https://nihcc.app.box.com/v/ChestXray-NIHCC
- RSNA 공식 다운로드: https://www.rsna.org/artificial-intelligence/ai-image-challenge/rsna-pneumonia-detection-challenge-2018
- 영상 ZIP: https://s3.amazonaws.com/east1.public.rsna.org/AI/2018/pneumonia-challenge-dataset-adjudicated-kaggle_2018.zip
- 주석 JSON: https://s3.amazonaws.com/east1.public.rsna.org/AI/2018/pneumonia-challenge-annotations-adjudicated-kaggle_2018.json
- 이용 조건: https://www.rsna.org/-/media/files/rsna/education/ai-resources-and-training/ai-image-challenge/pneumonia-detection-challenge-terms-of-use-and-attribution.pdf

공식 조건에 따라 대상자 식별·접촉을 시도하지 않아야 하며, 공유·재배포 시 출처와 다음 인용 정보를 유지해야 합니다.

1. Xiaosong Wang, Yifan Peng, Le Lu, Zhiyong Lu, Mohammadhadi Bagheri, Ronald Summers. ChestX-ray8: Hospital-scale Chest X-ray Database and Benchmarks on Weakly-Supervised Classification and Localization of Common Thorax Diseases. IEEE CVPR, pp. 3462–3471, 2017.
2. George Shih, Carol C. Wu, Safwan S. Halabi, Marc D. Kohli, Luciano M. Prevedello, Tessa S. Cook, Arjun Sharma, Judith K. Amorosa, Veronica Arteaga, Maya Galperin-Aizenberg, Ritu R. Gill, Myrna C.B. Godoy, Stephen Hobbs, Jean Jeudy, Archana Laroia, Palmi N. Shah, Dharshan Vummidi, Kavitha Yaddanapudi, Anouk Stein. Augmenting the National Institutes of Health Chest Radiograph Dataset with Expert Annotations of Possible Pneumonia. Radiology: Artificial Intelligence, 2019. https://doi.org/10.1148/ryai.2019180041

다운로드 날짜: 2026-09-22.

## 중증도 점수가 반드시 필요한 경우

BrixIA는 COVID-19 흉부 X-ray DICOM과 Brixia 점수를 제공합니다. 공식 사이트에서 등록 후 이메일로 다운로드 링크를 받는 절차가 필요합니다: https://brixia.github.io/ . 이번 묶음에는 BrixIA 자료가 포함되지 않았습니다.
