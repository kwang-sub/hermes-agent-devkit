package com.example.samples

import com.example.samples.error.ErrorCode
import com.example.samples.error.GlobalExceptionHandler
import com.example.samples.security.ApiAccessDeniedHandler
import com.example.samples.security.ApiAuthenticationEntryPoint
import com.fasterxml.jackson.databind.ObjectMapper
import io.swagger.v3.parser.OpenAPIV3Parser
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.DisplayName
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.http.MediaType
import org.springframework.mock.web.MockHttpServletRequest
import org.springframework.mock.web.MockHttpServletResponse
import org.springframework.security.access.AccessDeniedException
import org.springframework.security.authentication.BadCredentialsException
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.*
import java.nio.file.Files
import java.nio.file.Path

@DisplayName("오류 응답과 OpenAPI 통합 검증")
class ErrorAndOpenApiIntegrationTest : SampleIntegrationSupport() {
    @Autowired lateinit var mvc: MockMvc
    @Autowired lateinit var mapper: ObjectMapper

    @Test
    @DisplayName("등록된 업무 오류 코드는 서로 중복되지 않는다")
    fun `registry codes are unique`() {
        assertEquals(ErrorCode.values().size, ErrorCode.values().map { it.code }.toSet().size)
    }

    @Test
    @DisplayName("업무 오류의 HTTP 상태와 응답 본문이 일치한다")
    fun `business error HTTP status and body agree`() {
        mvc.perform(get("/api/sample/resources/999"))
            .andExpect(status().isNotFound).andExpect(jsonPath("$.code").value("RES_001"))
            .andExpect(jsonPath("$.status").value(404)).andExpect(jsonPath("$.path").value("/api/sample/resources/999"))
    }

    @Test
    @DisplayName("검증 실패와 잘못된 JSON에 안전한 400 응답을 반환한다")
    fun `validation and malformed JSON return safe 400 bodies`() {
        mvc.perform(post("/api/sample/resources").contentType(MediaType.APPLICATION_JSON).content("{\"name\":\"\"}"))
            .andExpect(status().isBadRequest).andExpect(jsonPath("$.code").value("REQ_002"))
            .andExpect(jsonPath("$.fieldErrors[0].field").value("name"))
            .andExpect(jsonPath("$.fieldErrors[0].rejectedValue").doesNotExist())
        val result = mvc.perform(post("/api/sample/resources").contentType(MediaType.APPLICATION_JSON)
            .content("{not-json-secret-fixture"))
            .andExpect(status().isBadRequest).andExpect(jsonPath("$.code").value("REQ_001"))
            .andReturn().response.contentAsString
        assertFalse(result.contains("not-json-secret-fixture"))
    }

    @Test
    @DisplayName("지원하지 않는 메서드는 Allow 헤더를 포함한 405 응답을 유지한다")
    fun `framework method rejection remains 405 with Allow header`() {
        mvc.perform(put("/api/sample/resources/1"))
            .andExpect(status().isMethodNotAllowed).andExpect(header().exists("Allow"))
            .andExpect(jsonPath("$.status").value(405))
    }

    @Test
    @DisplayName("예상하지 못한 오류의 내부 예외 메시지를 노출하지 않는다")
    fun `unexpected failures do not expose the exception message`() {
        val response = GlobalExceptionHandler().unexpected(IllegalStateException("database-password-fixture"), MockHttpServletRequest())
        assertEquals(500, response.statusCode.value())
        assertEquals(500, response.body!!.status)
        assertFalse(mapper.writeValueAsString(response.body).contains("database-password-fixture"))
    }

    @Test
    @DisplayName("인증과 인가 처리기가 동일한 오류 규격으로 401과 403을 반환한다")
    fun `security filter adapters use the same 401 and 403 contracts`() {
        val request = MockHttpServletRequest("GET", "/api/private")
        val unauthorized = MockHttpServletResponse()
        ApiAuthenticationEntryPoint(mapper).commence(request, unauthorized, BadCredentialsException("private-detail"))
        assertEquals(401, unauthorized.status)
        assertEquals("AUTH_001", mapper.readTree(unauthorized.contentAsByteArray)["code"].asText())
        val forbidden = MockHttpServletResponse()
        ApiAccessDeniedHandler(mapper).handle(request, forbidden, AccessDeniedException("private-detail"))
        assertEquals(403, forbidden.status)
        assertEquals("AUTH_002", mapper.readTree(forbidden.contentAsByteArray)["code"].asText())
        assertFalse(forbidden.contentAsString.contains("private-detail"))
    }

    @Test
    @DisplayName("생성된 OpenAPI가 규격을 통과하고 실제 오류 응답과 일치한다")
    fun `generated OpenAPI validates and matches actual errors`() {
        val json = mvc.perform(get("/v3/api-docs")).andExpect(status().isOk).andReturn().response.contentAsString
        val parsed = OpenAPIV3Parser().readContents(json, null, null)
        assertNotNull(parsed.openAPI)
        assertTrue(parsed.messages.isNullOrEmpty(), parsed.messages?.joinToString("\n"))
        val root = mapper.readTree(json)
        val response = root["paths"]["/api/sample/resources/{id}"]["get"]["responses"]["404"]
        assertTrue(response["description"].asText().isNotBlank())
        val media = response["content"]["application/json"]
        assertNotNull(media["schema"])
        val example = media["examples"]["RESOURCE_NOT_FOUND"]["value"]
        assertEquals("RES_001", example["code"].asText())
        assertEquals(404, example["status"].asInt())
        assertTrue(example["timestamp"].isTextual)
        val badRequest = root["paths"]["/api/sample/resources"]["post"]["responses"]["400"]["content"]["application/json"]["examples"]
        assertTrue(badRequest.has("INVALID_REQUEST") && badRequest.has("VALIDATION_FAILED"))
        val destination = Path.of(System.getProperty("sample.report.directory", "target"), "generated-openapi.json")
        Files.createDirectories(destination.parent)
        Files.writeString(destination, json)
    }
}
