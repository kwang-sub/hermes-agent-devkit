# Figma Provider Reference

## Canonical provider

Figma official REST API를 read-only로 사용한다.

- Authentication: https://developers.figma.com/docs/rest-api/authentication/
- Personal access token: https://developers.figma.com/docs/rest-api/personal-access-tokens/
- Plan access token: https://developers.figma.com/docs/rest-api/plan-access-tokens/
- File endpoints: https://developers.figma.com/docs/rest-api/file-endpoints/
- Official MCP: https://developers.figma.com/docs/figma-mcp-server/

## Endpoints

```text
GET /v1/files/:key/nodes?ids=<node-id>&depth=<n>
→ targeted node/context

GET /v1/files/:key?depth=<n>
→ bounded file read, --allow-file에서만

GET /v1/images/:key?ids=<node-id>&format=png&scale=1
→ rendered preview URL
```

`GET file`/`GET file nodes`/`GET image`는 `file_content:read` scope가 필요하다.

## Security

- token은 환경변수에서만 읽는다.
- request URL/query에 token을 넣지 않는다.
- API/HTTP error에 header/token을 출력하지 않는다.
- preview file은 `HERMES_WRITE_SAFE_ROOT` 안에만 저장한다.
- Figma write endpoint는 이 Skill에서 사용하지 않는다.

## Performance

- selected node URL을 우선한다.
- 기본 depth 4, 최대 6.
- file-level read는 명시적 `--allow-file`만 허용하고 실제 depth는 최대 2.
- raw response는 기본 비활성화한다.
- render는 실제 visual evidence가 필요할 때만 요청한다.
