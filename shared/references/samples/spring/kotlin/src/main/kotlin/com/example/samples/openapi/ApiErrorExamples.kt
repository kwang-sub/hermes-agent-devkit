package com.example.samples.openapi

import com.example.samples.error.ErrorCode

/** Declare only errors reachable from the endpoint; documentation does not enforce runtime behavior. */
@Target(AnnotationTarget.FUNCTION)
@Retention(AnnotationRetention.RUNTIME)
annotation class ApiErrorExamples(vararg val value: ErrorCode)
