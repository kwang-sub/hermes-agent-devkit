package com.example.samples.error

import org.springframework.http.HttpStatus

/** Sample-only vocabulary. Reuse a target project's error registry and wire codes. */
enum class ErrorCode(val status: HttpStatus, val code: String, val publicMessage: String) {
    INVALID_REQUEST(HttpStatus.BAD_REQUEST, "REQ_001", "Invalid request"),
    VALIDATION_FAILED(HttpStatus.BAD_REQUEST, "REQ_002", "Request validation failed"),
    RESOURCE_NOT_FOUND(HttpStatus.NOT_FOUND, "RES_001", "Resource not found"),
    DUPLICATE_RESOURCE(HttpStatus.CONFLICT, "RES_002", "Resource already exists"),
    UNAUTHENTICATED(HttpStatus.UNAUTHORIZED, "AUTH_001", "Authentication is required"),
    ACCESS_DENIED(HttpStatus.FORBIDDEN, "AUTH_002", "Access is denied"),
    INTERNAL_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "SYS_001", "An unexpected error occurred")
}
