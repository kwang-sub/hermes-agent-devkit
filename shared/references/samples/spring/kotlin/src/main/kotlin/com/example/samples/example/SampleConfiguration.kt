package com.example.samples.example

import com.example.samples.crypto.AesGcmEncryptor
import com.example.samples.crypto.EncryptedStringConverter
import com.example.samples.openapi.ErrorCodeOperationCustomizer
import com.fasterxml.jackson.databind.ObjectMapper
import org.springdoc.core.customizers.OperationCustomizer
import org.springframework.beans.factory.annotation.Value
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration

/** Explicit sample wiring, not auto-configuration. Missing encryption key fails startup. */
@Configuration(proxyBeanMethods = false)
class SampleConfiguration {
    @Bean
    fun sampleEncryptor(@Value("\${sample.crypto.key-base64}") key: String) = AesGcmEncryptor(key)

    @Bean
    fun encryptedStringConverter(encryptor: AesGcmEncryptor) = EncryptedStringConverter(encryptor)

    @Bean
    fun sampleErrorExamples(objectMapper: ObjectMapper): OperationCustomizer = ErrorCodeOperationCustomizer(objectMapper)
}
