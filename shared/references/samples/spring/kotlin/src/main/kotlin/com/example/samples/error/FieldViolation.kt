package com.example.samples.error

/** Rejected values are intentionally excluded; they may contain credentials or PII. */
data class FieldViolation(val field: String, val message: String)
