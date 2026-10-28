package com.example.samples.example

import com.example.samples.error.BusinessException
import com.example.samples.error.ErrorCode
import com.example.samples.openapi.ApiErrorExamples
import io.swagger.v3.oas.annotations.Operation
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

/** Demonstration endpoint only. No database, external calls or real business records. */
@RestController
@RequestMapping("/api/sample/resources")
class SampleResourceController {
    @Operation(summary = "Find a sample resource")
    @ApiErrorExamples(ErrorCode.RESOURCE_NOT_FOUND)
    @GetMapping("/{id}")
    fun find(@PathVariable id: Long): SampleResource {
        if (id != 1L) throw BusinessException(ErrorCode.RESOURCE_NOT_FOUND)
        return SampleResource(1, "sample")
    }

    @Operation(summary = "Validate a sample resource")
    @ApiErrorExamples(ErrorCode.INVALID_REQUEST, ErrorCode.VALIDATION_FAILED)
    @PostMapping
    fun validate(@Valid @RequestBody input: SampleResourceRequest) = SampleResource(1, input.name)
}

data class SampleResource(val id: Long, val name: String)
data class SampleResourceRequest(@field:NotBlank val name: String)
