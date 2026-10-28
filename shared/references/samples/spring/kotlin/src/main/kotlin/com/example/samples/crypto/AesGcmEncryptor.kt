package com.example.samples.crypto

import java.nio.ByteBuffer
import java.security.GeneralSecurityException
import java.security.SecureRandom
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Reference implementation of Base64(version | random IV | ciphertext + tag).
 * Not a key-management service. Preserve the application's existing ciphertext
 * format and key source when adapting this sample. Never log key or token values.
 */
class AesGcmEncryptor(base64Key: String) {
    private val key: SecretKeySpec
    private val random = SecureRandom()

    init {
        val bytes = try {
            Base64.getDecoder().decode(base64Key)
        } catch (_: IllegalArgumentException) {
            throw IllegalArgumentException("Encryption key must be valid Base64")
        }
        try {
            require(bytes.size == 32) { "AES-256 key must contain 32 bytes" }
            key = SecretKeySpec(bytes, "AES")
        } finally {
            bytes.fill(0)
        }
    }

    /** A new IV is required on every encryption, including repeated plaintext. */
    fun encrypt(plaintext: String, aad: ByteArray? = null): String {
        val iv = ByteArray(IV_BYTES).also(random::nextBytes)
        val input = plaintext.toByteArray(Charsets.UTF_8)
        try {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(TAG_BITS, iv))
            if (aad != null) cipher.updateAAD(aad)
            val ciphertext = cipher.doFinal(input)
            val payload = ByteBuffer.allocate(1 + iv.size + ciphertext.size)
                .put(VERSION).put(iv).put(ciphertext).array()
            return Base64.getEncoder().encodeToString(payload)
        } finally {
            input.fill(0)
        }
    }

    /** Invalid, truncated, unsupported or unauthenticated data never becomes plaintext. */
    fun decrypt(token: String, aad: ByteArray? = null): String {
        try {
            val payload = Base64.getDecoder().decode(token)
            require(payload.size >= 1 + IV_BYTES + TAG_BITS / 8)
            val buffer = ByteBuffer.wrap(payload)
            require(buffer.get() == VERSION)
            val iv = ByteArray(IV_BYTES).also(buffer::get)
            val ciphertext = ByteArray(buffer.remaining()).also(buffer::get)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(TAG_BITS, iv))
            if (aad != null) cipher.updateAAD(aad)
            val plaintext = cipher.doFinal(ciphertext)
            return try { String(plaintext, Charsets.UTF_8) } finally { plaintext.fill(0) }
        } catch (_: IllegalArgumentException) {
            throw IllegalArgumentException("Encrypted value is invalid or cannot be authenticated")
        } catch (_: GeneralSecurityException) {
            throw IllegalArgumentException("Encrypted value is invalid or cannot be authenticated")
        }
    }

    private companion object {
        const val IV_BYTES = 12
        const val TAG_BITS = 128
        const val VERSION: Byte = 1
    }
}
