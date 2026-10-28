package com.example.samples.security

import com.example.samples.error.ApiErrorResponse
import com.example.samples.error.ErrorCode
import com.fasterxml.jackson.databind.ObjectMapper
import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse
import org.springframework.http.MediaType
import org.springframework.security.access.AccessDeniedException
import org.springframework.security.web.access.AccessDeniedHandler

/** Optional filter-layer adapter; does not alter authentication or authorization policy. */
class ApiAccessDeniedHandler(private val objectMapper: ObjectMapper) : AccessDeniedHandler {
    override fun handle(request: HttpServletRequest, response: HttpServletResponse, ex: AccessDeniedException) {
        if (response.isCommitted) return
        response.status = ErrorCode.ACCESS_DENIED.status.value()
        response.contentType = MediaType.APPLICATION_JSON_VALUE
        objectMapper.writeValue(response.outputStream, ApiErrorResponse.from(ErrorCode.ACCESS_DENIED, request.requestURI))
    }
}
