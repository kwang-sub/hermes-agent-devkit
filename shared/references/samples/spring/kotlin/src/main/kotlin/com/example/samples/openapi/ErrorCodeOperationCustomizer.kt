package com.example.samples.openapi

import com.example.samples.error.ApiErrorResponse
import com.example.samples.error.ErrorCode
import com.fasterxml.jackson.databind.ObjectMapper
import io.swagger.v3.oas.models.Operation
import io.swagger.v3.oas.models.examples.Example
import io.swagger.v3.oas.models.media.ArraySchema
import io.swagger.v3.oas.models.media.Content
import io.swagger.v3.oas.models.media.IntegerSchema
import io.swagger.v3.oas.models.media.MediaType
import io.swagger.v3.oas.models.media.ObjectSchema
import io.swagger.v3.oas.models.media.Schema
import io.swagger.v3.oas.models.media.StringSchema
import io.swagger.v3.oas.models.responses.ApiResponse
import io.swagger.v3.oas.models.responses.ApiResponses
import org.springdoc.core.customizers.OperationCustomizer
import org.springframework.web.method.HandlerMethod
import java.time.Instant

/**
 * Enrich compatible inline responses; never replace project-owned contracts.
 * Unknown schemas, response refs, singular examples and other media types are
 * left intact. Adapt deliberately when an existing response wrapper is different.
 */
class ErrorCodeOperationCustomizer(private val objectMapper: ObjectMapper) : OperationCustomizer {
    override fun customize(operation: Operation, handlerMethod: HandlerMethod): Operation {
        val declaration = handlerMethod.getMethodAnnotation(ApiErrorExamples::class.java) ?: return operation
        if (operation.responses == null) operation.responses = ApiResponses()
        declaration.value.distinct().groupBy { it.status.value().toString() }.forEach { (status, codes) ->
            val response = operation.responses[status] ?: ApiResponse().also { operation.responses.addApiResponse(status, it) }
            merge(response, codes)
        }
        return operation
    }

    private fun merge(response: ApiResponse, codes: List<ErrorCode>) {
        if (response.`$ref` != null) return
        if (response.description.isNullOrBlank()) response.description = codes.first().status.reasonPhrase
        if (response.content == null) response.content = Content()
        // Do not introduce application/json beside a project-specific representation.
        if (response.content.isNotEmpty() && !response.content.containsKey("application/json")) return
        val media = response.content["application/json"] ?: MediaType().also { response.content.addMediaType("application/json", it) }
        val expectedSchema = errorSchema()
        if (media.schema != null && media.schema != expectedSchema) return
        // OpenAPI example and examples are mutually exclusive. Preserve either form.
        if (media.example != null) return
        if (media.schema == null && !media.examples.isNullOrEmpty()) return
        if (media.schema == null) media.schema = expectedSchema
        codes.forEach { code ->
            if (media.examples?.containsKey(code.name) != true) {
                val body = ApiErrorResponse.from(code, "/api/sample/resources/{id}", timestamp = Instant.EPOCH)
                val value: Map<*, *> = objectMapper.convertValue(body, Map::class.java)
                media.addExamples(code.name, Example().summary(code.publicMessage).value(value))
            }
        }
    }

    /** Inline schema avoids overwriting an application's components/schema registry. */
    private fun errorSchema(): Schema<*> = ObjectSchema()
        .addProperty("code", StringSchema()).addProperty("message", StringSchema())
        .addProperty("status", IntegerSchema()).addProperty("path", StringSchema())
        .addProperty("timestamp", StringSchema().format("date-time"))
        .addProperty("fieldErrors", ArraySchema().items(ObjectSchema()
            .addProperty("field", StringSchema()).addProperty("message", StringSchema())
            .required(listOf("field", "message"))))
        .required(listOf("code", "message", "status", "path", "timestamp", "fieldErrors"))
}
