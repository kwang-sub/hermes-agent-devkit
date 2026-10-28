package com.example.samples.error

/** Status and public message come from one registry, not independent constructor arguments. */
class BusinessException(val errorCode: ErrorCode, cause: Throwable? = null) :
    RuntimeException(errorCode.publicMessage, cause)
