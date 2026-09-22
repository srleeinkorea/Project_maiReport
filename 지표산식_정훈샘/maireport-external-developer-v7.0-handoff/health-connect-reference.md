# Health Connect 구현 참고

외부 개발자는 아래 Android 공식 문서를 기준으로 Health Connect record 필드와 aggregate
의미를 확인한다.

- [Health Connect data types](https://developer.android.com/health-and-fitness/health-connect/data-types)
  — StepsRecord, SleepSessionRecord, ExerciseSessionRecord와 read permission.
- [Health Connect data format](https://developer.android.com/health-and-fitness/health-connect/data-format)
  — 공통 timestamp, zone offset, metadata와 data origin/device.
- [Read data](https://developer.android.com/health-and-fitness/health-connect/read-data)
  — aggregate total과 data-origin/source 조회의 차이.
- [SleepSessionRecord API](https://developer.android.com/reference/androidx/health/connect/client/records/SleepSessionRecord)
  — session과 stage interval 구조.
- [SleepSessionRecord.Stage API](https://developer.android.com/reference/androidx/health/connect/client/records/SleepSessionRecord.Stage)
  — stage numeric constants.

이 문서들은 maiReport 산식을 정의하지 않는다. 산식에 입력할 수 있도록 어떤 원본 필드를
어떻게 정규화할지는 이 handoff의 `provider-field-map.json`, `preprocessing-rules.md`,
`formula-spec.md`를 따른다. 공식 문서와 실제 SDK 버전 사이에 차이가 있으면 provider
adapter에서 버전을 기록하고, 필드를 조용히 다른 의미로 변환하지 않는다.

Samsung Health 연동은 [Samsung Health Health Connect FAQ](https://developer.samsung.com/health/health-connect-faq.html)를
참고한다. 삼성헬스는 Health Connect에 걸음·운동·심박·수면을 동기화하며, Galaxy Watch
데이터는 삼성헬스를 거쳐 Health Connect로 전달될 수 있다. Samsung Health 원천의
package name은 `com.sec.android.app.shealth`로 provenance에서 확인한다.
