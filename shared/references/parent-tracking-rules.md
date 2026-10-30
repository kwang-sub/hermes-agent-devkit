# 선택적 Kanban 관계 기록

부모·자식 표시는 실행 의존성이 아닌 읽기용 관계다. 기존 카드 데이터와 dashboard 미리보기는 보존한다. DevKit에서 사용자가 관계 기록을 요청한 경우에만 다음 본문 형식을 사용한다.

```text
Parent Tracking:
- Parent Task ID: <existing-id>
- Relation: CHILD_WORK_UNIT
```

native task_links 생성·dispatch·자동 완료 전이는 하지 않는다. 자식 카드 완료가 기능 전체 구현 완료를 보장하지 않는다. 기존 parent/child 카드를 자동 재분류하거나 과거 알림을 재발송하지 않는다.
