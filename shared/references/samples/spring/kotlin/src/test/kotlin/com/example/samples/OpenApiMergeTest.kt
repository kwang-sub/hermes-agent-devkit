package com.example.samples

import com.example.samples.error.ErrorCode
import com.example.samples.openapi.ApiErrorExamples
import com.example.samples.openapi.ErrorCodeOperationCustomizer
import com.fasterxml.jackson.databind.SerializationFeature
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import io.swagger.v3.oas.models.Operation
import io.swagger.v3.oas.models.examples.Example
import io.swagger.v3.oas.models.headers.Header
import io.swagger.v3.oas.models.links.Link
import io.swagger.v3.oas.models.media.Content
import io.swagger.v3.oas.models.media.MediaType
import io.swagger.v3.oas.models.media.Schema
import io.swagger.v3.oas.models.responses.ApiResponse
import io.swagger.v3.oas.models.responses.ApiResponses
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.DisplayName
import org.junit.jupiter.api.Test
import org.springframework.web.method.HandlerMethod

@DisplayName("OpenAPI 오류 예시 병합 검증")
class OpenApiMergeTest {
    class Endpoint {
        @ApiErrorExamples(ErrorCode.INVALID_REQUEST, ErrorCode.VALIDATION_FAILED, ErrorCode.INVALID_REQUEST)
        fun documented() = Unit
        fun plain() = Unit
    }
    private val mapper = jacksonObjectMapper().findAndRegisterModules().disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
    private val customizer = ErrorCodeOperationCustomizer(mapper)
    private val handler = HandlerMethod(Endpoint(), Endpoint::class.java.getMethod("documented"))
    private fun operation(response: ApiResponse) = Operation().responses(ApiResponses().addApiResponse("400", response))

    @Test
    @DisplayName("오류 예시 어노테이션이 없는 API는 변경하지 않는다")
    fun `unannotated endpoints remain untouched`() {
        val operation = Operation()
        customizer.customize(operation, HandlerMethod(Endpoint(), Endpoint::class.java.getMethod("plain")))
        assertNull(operation.responses)
    }

    @Test
    @DisplayName("반복 적용해도 기존 설명과 헤더와 링크 및 호환 예시를 보존한다")
    fun `existing description headers links and compatible examples survive repeated customization`() {
        val response = ApiResponse().description("Project description")
            .addHeaderObject("X-Request-ID", Header().description("Project header"))
            .addLink("retry", Link().operationId("retryOperation"))
        val operation = operation(response)
        customizer.customize(operation, handler)
        val media = checkNotNull(response.content["application/json"])
        assertEquals(2, media.examples.size)
        val manual = Example().value(mapOf("code" to "preserve-me"))
        media.addExamples("INVALID_REQUEST", manual)
        val schema = media.schema
        customizer.customize(operation, handler)
        assertEquals("Project description", response.description)
        assertNotNull(response.headers["X-Request-ID"])
        assertNotNull(response.links["retry"])
        assertSame(manual, media.examples["INVALID_REQUEST"])
        assertSame(schema, media.schema)
        assertEquals(2, media.examples.size)
    }

    @Test
    @DisplayName("다른 응답 스키마에 맞지 않는 예시를 주입하지 않는다")
    fun `foreign schema is preserved without injecting mismatched sample examples`() {
        val schema = Schema<Any>().`$ref`("#/components/schemas/ExistingWrapper")
        val media = MediaType().schema(schema)
        val response = ApiResponse().description("Existing").content(Content().addMediaType("application/json", media))
        customizer.customize(operation(response), handler)
        assertSame(schema, media.schema)
        assertNull(media.examples)
    }

    @Test
    @DisplayName("응답 참조와 JSON이 아닌 표현을 보존한다")
    fun `response refs and non-JSON representations are preserved`() {
        val reference = ApiResponse().`$ref`("#/components/responses/ExistingError")
        customizer.customize(operation(reference), handler)
        assertNull(reference.content)
        assertNull(reference.description)
        val response = ApiResponse().description("Problem detail").content(Content().addMediaType("application/problem+json", MediaType()))
        customizer.customize(operation(response), handler)
        assertEquals(setOf("application/problem+json"), response.content.keys)
    }

    @Test
    @DisplayName("단일 example과 복수 examples를 함께 생성하지 않는다")
    fun `singular example is not combined with examples`() {
        val value = mapOf("message" to "existing")
        val media = MediaType().example(value)
        val response = ApiResponse().content(Content().addMediaType("application/json", media))
        customizer.customize(operation(response), handler)
        assertEquals(value, media.example)
        assertNull(media.examples)
    }
}
