# dev-infrastructure

애플리케이션/DB의 실행 위치와 DB platform/vendor를 독립 축으로 관리하는 Infrastructure canonical entry다.

기본 desired runtime은 Application/Database 모두 `CONTAINER`이며, 기존 repository의 observed evidence를 기본값으로 덮어쓰지 않는다.

```bash
python3 scripts/detect_infrastructure.py --repo /workspace/project
python3 scripts/plan_transition.py --repo /workspace/project
```

DB vendor가 바뀌면 `dev-data-feature`와 `dev-db-migration`을 함께 적용한다. Runtime만 바뀌는 경우 기존 persistent data는 자동 삭제하지 않는다.
