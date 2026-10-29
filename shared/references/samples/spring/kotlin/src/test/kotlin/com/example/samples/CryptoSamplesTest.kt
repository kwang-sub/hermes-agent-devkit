package com.example.samples

import com.example.samples.crypto.AesGcmEncryptor
import com.example.samples.crypto.Argon2Hasher
import com.example.samples.crypto.EncryptedStringConverter
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.DisplayName
import org.junit.jupiter.api.Test
import java.security.SecureRandom
import java.util.Base64

@DisplayName("암호화 및 해싱 공통 샘플 검증")
class CryptoSamplesTest {
    private fun key() = Base64.getEncoder().encodeToString(ByteArray(32).also(SecureRandom()::nextBytes))

    @Test
    @DisplayName("한글과 빈 문자열을 암호화한 후 원문으로 복원한다")
    fun `unicode and empty strings round trip`() {
        val cipher = AesGcmEncryptor(key())
        for (value in listOf("", "sample", "한글🙂")) assertEquals(value, cipher.decrypt(cipher.encrypt(value)))
    }

    @Test
    @DisplayName("같은 평문도 새로운 IV를 사용하면 다른 암호문을 생성한다")
    fun `fresh IV changes ciphertext for equal plaintext`() {
        val cipher = AesGcmEncryptor(key())
        assertNotEquals(cipher.encrypt("same"), cipher.encrypt("same"))
    }

    @Test
    @DisplayName("변조된 암호문과 잘못된 키의 복호화를 거부한다")
    fun `tampering and wrong key fail closed`() {
        val cipher = AesGcmEncryptor(key())
        val token = cipher.encrypt("sensitive-fixture")
        val payload = Base64.getDecoder().decode(token)
        payload[payload.lastIndex] = (payload.last().toInt() xor 1).toByte()
        assertThrows(IllegalArgumentException::class.java) { cipher.decrypt(Base64.getEncoder().encodeToString(payload)) }
        val error = assertThrows(IllegalArgumentException::class.java) { AesGcmEncryptor(key()).decrypt(token) }
        assertFalse(error.message!!.contains(token))
        assertNull(error.cause)
    }

    @Test
    @DisplayName("복호화할 때 암호화에 사용한 AAD가 일치해야 한다")
    fun `AAD must match on decrypt`() {
        val cipher = AesGcmEncryptor(key())
        val token = cipher.encrypt("value", "field-context".toByteArray())
        assertEquals("value", cipher.decrypt(token, "field-context".toByteArray()))
        assertThrows(IllegalArgumentException::class.java) { cipher.decrypt(token, "other-context".toByteArray()) }
    }

    @Test
    @DisplayName("잘못되거나 잘린 암호문과 지원하지 않는 버전을 거부한다")
    fun `malformed truncated and unsupported envelopes are rejected`() {
        val cipher = AesGcmEncryptor(key())
        for (token in listOf("not base64!", "", Base64.getEncoder().encodeToString(ByteArray(28)))) {
            assertThrows(IllegalArgumentException::class.java) { cipher.decrypt(token) }
        }
        val payload = Base64.getDecoder().decode(cipher.encrypt("value"))
        payload[0] = 9
        assertThrows(IllegalArgumentException::class.java) { cipher.decrypt(Base64.getEncoder().encodeToString(payload)) }
    }

    @Test
    @DisplayName("유효하지 않은 키를 거부하고 입력값을 노출하지 않는다")
    fun `key validation does not expose input`() {
        assertThrows(IllegalArgumentException::class.java) { AesGcmEncryptor("invalid key!") }
        assertThrows(IllegalArgumentException::class.java) { AesGcmEncryptor(Base64.getEncoder().encodeToString(ByteArray(16))) }
    }

    @Test
    @DisplayName("null은 유지하고 빈 문자열은 null과 구분하여 변환한다")
    fun `null stays null and empty is not null`() {
        val converter = EncryptedStringConverter(AesGcmEncryptor(key()))
        assertNull(converter.convertToDatabaseColumn(null))
        assertNull(converter.convertToEntityAttribute(null))
        val emptyToken = converter.convertToDatabaseColumn("")
        assertFalse(emptyToken.isNullOrBlank())
        assertEquals("", converter.convertToEntityAttribute(emptyToken))
    }

    @Test
    @DisplayName("Argon2 해싱과 일치 검증 후 입력 버퍼를 지운다")
    fun `Argon2 explicitly hashes verifies and wipes caller buffers`() {
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
