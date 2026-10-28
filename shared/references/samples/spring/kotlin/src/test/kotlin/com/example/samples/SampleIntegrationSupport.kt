package com.example.samples

import com.example.samples.crypto.EncryptedStringConverter
import com.example.samples.error.GlobalExceptionHandler
import com.example.samples.example.SampleConfiguration
import com.example.samples.example.SampleResourceController
import jakarta.persistence.*
import org.springframework.boot.SpringBootConfiguration
import org.springframework.boot.autoconfigure.EnableAutoConfiguration
import org.springframework.boot.autoconfigure.domain.EntityScan
import org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.context.annotation.Import
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import java.security.SecureRandom
import java.util.Base64

@SpringBootConfiguration(proxyBeanMethods = false)
@EnableAutoConfiguration(exclude = [SecurityAutoConfiguration::class])
@EntityScan(basePackageClasses = [SecretRecord::class])
@Import(SampleConfiguration::class, SampleResourceController::class, GlobalExceptionHandler::class)
class SampleTestApplication

@Entity
@Table(name = "sample_secret_record")
open class SecretRecord(
    @field:Id @field:GeneratedValue(strategy = GenerationType.IDENTITY) open var id: Long? = null,
    @field:Convert(converter = EncryptedStringConverter::class)
    @field:Column(name = "encrypted_value", length = 2048) open var value: String? = null,
    @field:Column(name = "plain_label") open var label: String = "fixture"
)

@SpringBootTest(classes = [SampleTestApplication::class], properties = [
    "spring.datasource.url=jdbc:h2:mem:reference_samples;DB_CLOSE_DELAY=-1",
    "spring.jpa.hibernate.ddl-auto=create-drop",
    "spring.jpa.open-in-view=false",
    "springdoc.override-with-generic-response=false"
])
@AutoConfigureMockMvc
abstract class SampleIntegrationSupport {
    companion object {
        private val ephemeralKey = Base64.getEncoder().encodeToString(ByteArray(32).also(SecureRandom()::nextBytes))
        @JvmStatic @DynamicPropertySource
        fun sampleProperties(registry: DynamicPropertyRegistry) {
            registry.add("sample.crypto.key-base64") { ephemeralKey }
        }
    }
}
