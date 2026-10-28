package com.example.samples

import com.example.samples.crypto.AesGcmEncryptor
import com.example.samples.crypto.Argon2Hasher
import com.example.samples.crypto.EncryptedStringConverter
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import java.security.SecureRandom
import java.util.Base64

class CryptoSamplesTest {
    private fun key() = Base64.getEncoder().encodeToString(ByteArray(32).also(SecureRandom()::nextBytes))

    @Test fun `unicode and empty strings round trip`() {
        val cipher = AesGcmEncryptor(key())
        for (value in listOf("", "sample", "한글🙂")) assertEquals(value, cipher.decrypt(cipher.encrypt(value)))
    }

    @Test fun `fresh IV changes ciphertext for equal plaintext`() {
        val cipher = AesGcmEncryptor(key())
        assertNotEquals(cipher.encrypt("same"), cipher.encrypt("same"))
    }

    @Test fun `tampering and wrong key fail closed`() {
        val cipher = AesGcmEncryptor(key())
        val token = cipher.encrypt("sensitive-fixture")
        val payload = Base64.getDecoder().decode(token)
        payload[payload.lastIndex] = (payload.last().toInt() xor 1).toByte()
        assertThrows(IllegalArgumentException::class.java) { cipher.decrypt(Base64.getEncoder().encodeToString(payload)) }
        val error = assertThrows(IllegalArgumentException::class.java) { AesGcmEncryptor(key()).decrypt(token) }
        assertFalse(error.message!!.contains(token))
        assertNull(error.cause)
    }

    @Test fun `AAD must match on decrypt`() {
        val cipher = AesGcmEncryptor(key())
        val token = cipher.encrypt("value", "field-context".toByteArray())
        assertEquals("value", cipher.decrypt(token, "field-context".toByteArray()))
        assertThrows(IllegalArgumentException::class.java) { cipher.decrypt(token, "other-context".toByteArray()) }
    }

    @Test fun `malformed truncated and unsupported envelopes are rejected`() {
        val cipher = AesGcmEncryptor(key())
        for (token in listOf("not base64!", "", Base64.getEncoder().encodeToString(ByteArray(28)))) {
            assertThrows(IllegalArgumentException::class.java) { cipher.decrypt(token) }
        }
        val payload = Base64.getDecoder().decode(cipher.encrypt("value"))
        payload[0] = 9
        assertThrows(IllegalArgumentException::class.java) { cipher.decrypt(Base64.getEncoder().encodeToString(payload)) }
    }

    @Test fun `key validation does not expose input`() {
        assertThrows(IllegalArgumentException::class.java) { AesGcmEncryptor("invalid key!") }
        assertThrows(IllegalArgumentException::class.java) { AesGcmEncryptor(Base64.getEncoder().encodeToString(ByteArray(16))) }
    }

    @Test fun `null stays null and empty is not null`() {
        val converter = EncryptedStringConverter(AesGcmEncryptor(key()))
        assertNull(converter.convertToDatabaseColumn(null))
        assertNull(converter.convertToEntityAttribute(null))
        val emptyToken = converter.convertToDatabaseColumn("")
        assertFalse(emptyToken.isNullOrBlank())
        assertEquals("", converter.convertToEntityAttribute(emptyToken))
    }

    @Test fun `Argon2 explicitly hashes verifies and wipes caller buffers`() {
        val hasher = Argon2Hasher()
        val raw = "example-password".toCharArray()
        val encoded = hasher.hash(raw)
        assertTrue(raw.all { it == '\u0000' })
        assertTrue(encoded.startsWith("\$argon2id\$"))
        val matching = "example-password".toCharArray()
        assertTrue(hasher.matches(encoded, matching))
        assertTrue(matching.all { it == '\u0000' })
        val wrong = "incorrect".toCharArray()
        assertFalse(hasher.matches(encoded, wrong))
        assertTrue(wrong.all { it == '\u0000' })
        val malformed = "value".toCharArray()
        assertThrows(IllegalArgumentException::class.java) { hasher.matches("not-an-encoded-hash", malformed) }
        assertTrue(malformed.all { it == '\u0000' })
    }
}
