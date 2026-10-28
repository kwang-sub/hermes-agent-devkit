package com.example.samples.crypto

import de.mkammerer.argon2.Argon2Factory

/**
 * Explicit one-way hashing at the service boundary, NOT an AttributeConverter.
 * Both methods consume and wipe the caller's character array even on failure.
 * Parameters reproduce the reference baseline; benchmark against deployment limits.
 * A stored hash is passed to matches(), never automatically hashed on entity update.
 */
class Argon2Hasher {
    fun hash(raw: CharArray): String = try {
        Argon2Factory.create(Argon2Factory.Argon2Types.ARGON2id).hash(3, 65536, 1, raw)
    } finally {
        raw.fill('\u0000')
    }

    fun matches(encoded: String, raw: CharArray): Boolean = try {
        require(encoded.startsWith("\$argon2id\$")) { "Stored hash must use the configured Argon2id format" }
        Argon2Factory.create(Argon2Factory.Argon2Types.ARGON2id).verify(encoded, raw)
    } finally {
        raw.fill('\u0000')
    }
}
