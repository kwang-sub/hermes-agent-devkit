package com.example.samples.crypto

import jakarta.persistence.AttributeConverter
import jakarta.persistence.Converter

/**
 * Opt-in field conversion; do not automatically encrypt every String attribute.
 * Constructor injection here relies on Spring Boot + Hibernate bean integration,
 * not portable JPA alone. An actual EntityManager round-trip test accompanies it.
 */
@Converter(autoApply = false)
class EncryptedStringConverter(private val encryptor: AesGcmEncryptor) : AttributeConverter<String, String> {
    override fun convertToDatabaseColumn(attribute: String?): String? = attribute?.let(encryptor::encrypt)
    override fun convertToEntityAttribute(dbData: String?): String? = dbData?.let(encryptor::decrypt)
}
