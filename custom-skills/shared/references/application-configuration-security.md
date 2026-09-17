# Application Configuration Security

애플리케이션의 접속 정보, 인증 키, 비밀번호, 토큰, 환경별 endpoint를 Git 소스와 분리하기 위한 공통 계약이다.

## 1. 이름 규칙

관행을 우선한다.

```text
.env.example   = Git 추적 가능한 환경변수 계약
.env.local     = 로컬 실제값, Git ignore
.env           = runtime/container 실제값, Git ignore
```

`sample.env`, `sample_application.yml` 같은 별도 이름을 새 표준으로 만들지 않는다. 기존 프로젝트가 이미 다른 관행을 명시적으로 사용하는 경우에는 기존 계약을 보존한다.

## 2. 공통 원칙

```text
Git-tracked configuration
→ 구조 / 변수명 / placeholder / 공개 가능한 정적 설정

Local/runtime configuration
→ 실제 DB credential / secret / token / 환경별 endpoint / 실제 publishable key
```

공개 가능한 값과 Git에 실제 값을 저장해도 좋은 값은 같은 개념이 아니다. 브라우저에 공개되는 publishable key도 개발/스테이징/운영 환경을 분리하기 위해 실제 값은 runtime environment에 둔다.

`.env.example`에는 실제 credential이나 실제 environment-specific key 값을 복사하지 않는다. 필요한 변수명만 `KEY=` 형태로 둔다.

기존 프로젝트는 **Preserve First**다. 이미 Git에 추적 중인 설정을 Bootstrap이 자동 치환, 삭제, untrack하지 않는다. 보안상 권장되지 않는 상태를 발견하면 값 자체를 출력하지 않고 파일/키 이름만 `WARN`으로 보고한 뒤 Bootstrap을 계속한다.

## 3. Spring Boot

공통 `application.yml` / `application.yaml` / `application.properties`는 모두 지원하며 Git 추적을 유지한다. 신규/수정 구성에서는 실제 접속값을 placeholder로 바인딩하는 방식을 우선한다.

YAML 예:

```yaml
spring:
  datasource:
    url: ${DB_URL}
    username: ${DB_USERNAME}
    password: ${DB_PASSWORD}

supabase:
  url: ${SUPABASE_URL}
  secret-key: ${SUPABASE_SECRET_KEY}
```

Properties 예:

```properties
spring.datasource.url=${DB_URL}
spring.datasource.username=${DB_USERNAME}
spring.datasource.password=${DB_PASSWORD}
supabase.url=${SUPABASE_URL}
supabase.secret-key=${SUPABASE_SECRET_KEY}
```

`application.yml`, `application.yaml`, `application.properties`의 `${ENV_VAR}` placeholder는 동일하게 감지하여 `.env.example` 변수 계약에 반영한다. 하드코딩 탐지도 YAML과 Properties 양쪽에 동일하게 적용한다.

Spring Boot가 `${DB_USERNAME}`를 해석할 때는 Spring Environment의 property source를 사용한다. 로컬 실행에서는 IntelliJ Run Configuration 또는 OS environment variable을 사용하고, container 실행에서는 Docker/Compose가 container environment로 주입한다.

중요:

```text
Spring Boot 자체는 일반적인 .env 파일을 자동 로드하지 않는다.
```

따라서 `.env` 파일을 사용하는 경우 이를 읽어 Spring process의 environment로 전달하는 주체가 명확해야 한다. 현재 Container runtime에서는 Compose `env_file`/environment가 그 역할을 할 수 있다. LOCAL_HOST에서는 IntelliJ/OS environment를 기본 계약으로 한다.

`application-local.yml`, `application-local.properties`, `application-secret.*`, `application-private.*` 계열에 실제값을 두는 기존 프로젝트는 사용할 수 있지만 이 파일들은 Git ignore 대상이다. 신규 구성에서는 공통 `application.*` + environment variable 방식을 우선한다.

기존 프로젝트 예:

```properties
spring.datasource.url=jdbc:postgresql://localhost:5432/app
spring.datasource.username=app_user
spring.datasource.password=existing-password
```

Bootstrap은 이를 자동으로 `${DB_*}` 형태로 바꾸지 않는다. 다음처럼 경고만 남기고 기존 상태를 보존한다.

```text
[WARN] ... application.properties:spring.datasource.password ... preserving existing value.
CONFIG_SECURITY=warn
BOOTSTRAP=CONTINUE
```

## 4. Frontend / Next.js

Next.js 로컬 실제값은 `.env.local`에 둔다.

```text
frontend/
├─ .env.example   Git O
└─ .env.local     Git X
```

예:

```dotenv
# .env.example
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
```

`NEXT_PUBLIC_*` 값은 browser bundle에서 사용자가 볼 수 있다. 따라서 이를 secret으로 취급하지 않는다. 그러나 실제 Supabase project URL/publishable key는 환경별 runtime configuration이므로 Git에는 실제 값을 넣지 않고 `.env.local`/deployment environment에서 주입한다.

`SUPABASE_SECRET_KEY`, service role 계열, OAuth client secret, private API token은 browser-visible 코드 또는 `NEXT_PUBLIC_*` 변수로 노출하면 안 된다. Server Component/Route Handler/backend 등 server-only 경계에서만 사용한다.

## 5. 공개키 / 비밀키

```text
*-public.pem   Git 추적 가능
*-private.pem  Git ignore
private.pem    Git ignore
*.p12 / *.pfx / *.jks  Git ignore 기본값
```

공개키는 공개를 전제로 한 암호학적 material이므로 Git 추적이 가능하다. private key/keystore는 실제 credential로 취급한다.

## 6. Bootstrap 안전 규칙

Bootstrap은 다음을 보장한다.

1. `.env`, `.env.*`를 ignore하고 `.env.example`은 추적 가능하게 유지한다.
2. Spring local/private config와 private key/keystore를 ignore한다.
3. Backend/Frontend app root에 `.env.example`이 없으면 생성한다.
4. 기존 local env 파일에서 example을 만들 때 **값은 복사하지 않고 key 이름만 추출**한다.
5. Spring `application.yml`, `application.yaml`, `application.properties`의 `${ENV_VAR}` placeholder를 `.env.example` 계약에 반영한다.
6. 이미 Git 추적 중인 protected local/secret 파일은 자동 `git rm --cached`하지 않는다. `WARN` 후 그대로 보존하고 Bootstrap을 계속한다.
7. tracked Spring 공통 설정에 password/secret/token/private key 또는 환경별 datasource/Supabase 값이 하드코딩되어 있으면 자동 치환하지 않는다. `WARN` 후 그대로 보존하고 Bootstrap을 계속한다.
8. 경고에는 실제 secret 값 대신 `relative/path:key`만 출력한다.
9. 기존 `.env.example`은 덮어쓰지 않는다.
10. 신규 Hermes/Coder 설정은 가능한 경우 environment placeholder 방식으로 생성한다.

Bootstrap 설정 보안의 기본 모드는 다음과 같다.

```text
Existing project
→ DETECT
→ WARN
→ PRESERVE
→ CONTINUE

New/changed configuration
→ SECURE BY DEFAULT
→ ${ENV_VAR} / .env.example / runtime environment
```

## 7. Runtime 별 전달 경로

```text
Application Runtime = LOCAL_HOST
Spring  : IntelliJ / OS Environment -> Spring Environment -> ${...}
Next.js : .env.local -> Next.js runtime

Application Runtime = CONTAINER
.env / deployment env -> Compose/container environment -> application

Application Runtime = NETWORK_HOST
CI/CD secret or remote runtime environment -> application process
```

`.env.example`은 실행용 secret store가 아니라 **환경변수 계약 문서**다.
