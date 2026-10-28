package com.example.samples.error

import java.time.Instant

/** Illustrative response only; never replace an established application response contract. */
data class ApiErrorResponse(
    val code: String,
    val message: String,
    val status: Int,
    val path: String,
    val timestamp: Instant,
    val fieldErrors: List<FieldViolation> = emptyList()
) {
    companion object {
        fun from(error: ErrorCode, path: String, fields: List<FieldViolation> = emptyList(),
                 timestamp: Instant = Instant.now()) =
            ApiErrorResponse(error.code, error.publicMessage, error.status.value(), path, timestamp, fields)
    }
}
