# 역할 독립 Maven·Gradle 검증

이 폴더가 canonical implementation이다. 이미지의 `/opt/devkit/scripts/verification/`에 그대로 설치한다. engine은 `/opt/devkit/custom-skills/_lib/process_execution.py`를 사용한다. 더 이상 Coder/Reviewer 디렉터리에 복사본을 유지하지 않는다.

프로젝트의 기존 toolchain과 승인된 명령, 명시적인 `--scope-path`를 사용한다. `*_verification_cached.py`는 성공한 동일 request/scope의 증거만 재사용한다. 외부 환경·시간에 의존하면 `--no-reuse`를 지정한다. 코드/테스트/build/toolchain 변경과 실행 중 source 변경은 이전 PASS를 무효화한다. 환경변수의 과거 Task ID는 캐시 namespace의 선택적 값일 뿐 Task·Worker 소유권이 필요하지 않다.

Maven은 `hermes-maven`, Gradle은 `hermes-java`를 통한 Linux 산출물·캐시 격리와 실행 제한을 유지한다. 기능 테스트가 필요한 변경은 compile PASS만으로 검증 완료 처리하지 않는다.
