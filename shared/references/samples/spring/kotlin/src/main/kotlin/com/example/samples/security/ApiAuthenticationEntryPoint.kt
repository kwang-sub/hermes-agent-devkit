package com.example.samples.security

import com.example.samples.error.ApiErrorResponse
import com.example.samples.error.ErrorCode
import com.fasterxml.jackson.databind.ObjectMapper
import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse
import org.springframework.http.MediaType
import org.springframework.security.core.AuthenticationException
import org.springframework.security.web.AuthenticationEntryPoint

/** Optional filter-layer adapter; wire into the EXISTING SecurityFilterChain explicitly. */
class ApiAuthenticationEntryPoint(private val objectMapper: ObjectMapper) : AuthenticationEntryPoint {
    override fun commence(request: HttpServletRequest, response: HttpServletResponse, ex: AuthenticationException) {
        if (response.isCommitted) return
        response.status = ErrorCode.UNAUTHENTICATED.status.value()
        response.contentType = MediaType.APPLICATION_JSON_VALUE
        objectMapper.writeValue(response.outputStream, ApiErrorResponse.from(ErrorCode.UNAUTHENTICATED, request.requestURI))
    }
}
