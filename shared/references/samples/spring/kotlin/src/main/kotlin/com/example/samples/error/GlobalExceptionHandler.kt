package com.example.samples.error

import jakarta.servlet.http.HttpServletRequest
import org.slf4j.LoggerFactory
import org.springframework.http.HttpHeaders
import org.springframework.http.HttpStatus
import org.springframework.http.HttpStatusCode
import org.springframework.http.ResponseEntity
import org.springframework.http.converter.HttpMessageNotReadableException
import org.springframework.security.access.AccessDeniedException
import org.springframework.security.core.AuthenticationException
import org.springframework.web.bind.MethodArgumentNotValidException
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.RestControllerAdvice
import org.springframework.web.context.request.ServletWebRequest
import org.springframework.web.context.request.WebRequest
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler
import java.time.Instant

/**
 * Opt-in example: adapt the existing advice instead of registering a second handler.
 * ResponseEntityExceptionHandler preserves framework status/headers (e.g. 405 Allow).
 * No exception messages, rejected values, SQL or stack traces are exposed to clients.
 */
@RestControllerAdvice
class GlobalExceptionHandler : ResponseEntityExceptionHandler() {
    private val log = LoggerFactory.getLogger(javaClass)

    @ExceptionHandler(BusinessException::class)
    fun business(ex: BusinessException, request: HttpServletRequest): ResponseEntity<ApiErrorResponse> =
        ResponseEntity.status(ex.errorCode.status).body(ApiErrorResponse.from(ex.errorCode, request.requestURI))

    @ExceptionHandler(AuthenticationException::class)
    fun unauthenticated(request: HttpServletRequest): ResponseEntity<ApiErrorResponse> =
        ResponseEntity.status(401).body(ApiErrorResponse.from(ErrorCode.UNAUTHENTICATED, request.requestURI))

    @ExceptionHandler(AccessDeniedException::class)
    fun forbidden(request: HttpServletRequest): ResponseEntity<ApiErrorResponse> =
        ResponseEntity.status(403).body(ApiErrorResponse.from(ErrorCode.ACCESS_DENIED, request.requestURI))

    @ExceptionHandler(Exception::class)
    fun unexpected(ex: Exception, request: HttpServletRequest): ResponseEntity<ApiErrorResponse> {
        // Project-specific observability may add a correlation ID, never raw request values.
        log.error("Unexpected request failure; exceptionType={}", ex.javaClass.simpleName)
        return ResponseEntity.status(500).body(ApiErrorResponse.from(ErrorCode.INTERNAL_ERROR, request.requestURI))
    }

    override fun handleMethodArgumentNotValid(ex: MethodArgumentNotValidException, headers: HttpHeaders,
        status: HttpStatusCode, request: WebRequest): ResponseEntity<Any>? {
        // Constraint messages can interpolate rejected values; use a safe sample message.
        val fields = ex.bindingResult.fieldErrors.map { FieldViolation(it.field, "Invalid field value") }
        return ResponseEntity.status(status).headers(headers)
            .body(ApiErrorResponse.from(ErrorCode.VALIDATION_FAILED, path(request), fields))
    }

    override fun handleHttpMessageNotReadable(ex: HttpMessageNotReadableException, headers: HttpHeaders,
        status: HttpStatusCode, request: WebRequest): ResponseEntity<Any>? =
        ResponseEntity.status(status).headers(headers).body(ApiErrorResponse.from(ErrorCode.INVALID_REQUEST, path(request)))

    override fun handleExceptionInternal(ex: Exception, body: Any?, headers: HttpHeaders,
        statusCode: HttpStatusCode, request: WebRequest): ResponseEntity<Any>? {
        if ((request as? ServletWebRequest)?.response?.isCommitted == true) return null
        val response = ApiErrorResponse(
            "HTTP_${statusCode.value()}", HttpStatus.resolve(statusCode.value())?.reasonPhrase ?: "Request failed",
            statusCode.value(), path(request), Instant.now()
        )
        return ResponseEntity.status(statusCode).headers(headers).body(response)
    }

    private fun path(request: WebRequest): String = (request as? ServletWebRequest)?.request?.requestURI ?: ""
}
