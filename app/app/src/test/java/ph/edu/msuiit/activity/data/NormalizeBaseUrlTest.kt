package ph.edu.msuiit.activity.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NormalizeBaseUrlTest {

    @Test
    fun addsSchemeAndTrimsSlashesAndSpaces() {
        assertEquals("http://172.20.10.2:8000", normalizeBaseUrl("  172.20.10.2:8000/ "))
        assertEquals("http://10.0.2.2:8000", normalizeBaseUrl("http://10.0.2.2:8000//"))
        assertEquals("https://example.com", normalizeBaseUrl("HTTPS://example.com"))
    }

    @Test
    fun rejectsUnusableAddresses() {
        assertNull(normalizeBaseUrl(""))
        assertNull(normalizeBaseUrl("   "))
        assertNull(normalizeBaseUrl("ftp://host"))
        assertNull(normalizeBaseUrl("http://"))
        assertNull(normalizeBaseUrl("http://my host"))
        assertNull(normalizeBaseUrl("http://host/api")) // the app adds /api itself
    }
}
