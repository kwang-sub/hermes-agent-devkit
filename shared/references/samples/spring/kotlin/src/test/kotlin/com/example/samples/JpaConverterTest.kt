package com.example.samples

import jakarta.persistence.EntityManager
import jakarta.persistence.PersistenceContext
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.DisplayName
import org.junit.jupiter.api.Test
import org.springframework.transaction.annotation.Transactional

@Transactional
@DisplayName("JPA 암호화 컨버터 영속성 검증")
class JpaConverterTest : SampleIntegrationSupport() {
    @PersistenceContext lateinit var entityManager: EntityManager

    @Test
    @DisplayName("실제 Hibernate 컨버터 주입으로 암호문을 저장하고 평문을 조회한다")
    fun `actual Hibernate converter injection persists ciphertext and reads plaintext`() {
        val record = SecretRecord(value = "private-fixture", label = "unchanged-label")
        entityManager.persist(record)
        entityManager.flush()
        val stored = entityManager.createNativeQuery("select encrypted_value from sample_secret_record where id = :id")
            .setParameter("id", record.id).singleResult as String
        assertNotEquals("private-fixture", stored)
        assertFalse(stored.contains("private-fixture"))
        entityManager.clear()
        val loaded = entityManager.find(SecretRecord::class.java, record.id)
        assertEquals("private-fixture", loaded.value)
        assertEquals("unchanged-label", loaded.label)
        loaded.label = "updated-label"
        entityManager.flush()
        entityManager.clear()
        assertEquals("private-fixture", entityManager.find(SecretRecord::class.java, record.id).value)
    }

    @Test
    @DisplayName("null 저장 후 평문 갱신 값을 다시 조회할 수 있다")
    fun `null persistence and subsequent plaintext update round trip`() {
        val record = SecretRecord(value = null)
        entityManager.persist(record)
        entityManager.flush()
        entityManager.clear()
        val loaded = entityManager.find(SecretRecord::class.java, record.id)
        assertNull(loaded.value)
        loaded.value = "replacement"
        entityManager.flush()
        entityManager.clear()
        assertEquals("replacement", entityManager.find(SecretRecord::class.java, record.id).value)
    }
}
