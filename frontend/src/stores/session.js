/**
 * Session Store - Authentication State Management
 *
 * Manages:
 * - User authentication state
 * - Token persistence
 * - User profile
 * - Organization context
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE = '/api/v1'

export const useSessionStore = defineStore('session', () => {
    // State
    const token = ref(localStorage.getItem('auth_token') || null)
    const user = ref(null)
    const orgContext = ref(null)
    const roles = ref([])
    const loading = ref(false)
    const error = ref(null)

    // Computed
    const isAuthenticated = computed(() => !!token.value)

    const userInitials = computed(() => {
        if (!user.value?.email) return '??'
        return user.value.email.substring(0, 2).toUpperCase()
    })

    const userDisplayName = computed(() => {
        if (user.value?.name) return user.value.name
        if (user.value?.email) return user.value.email.split('@')[0]
        return 'User'
    })

    // Actions
    async function login(username, password) {
        loading.value = true
        error.value = null

        try {
            const response = await fetch(`${API_BASE}/auth/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            })

            if (!response.ok) {
                const data = await response.json().catch(() => ({}))
                if (response.status === 401) {
                    throw new Error(data.detail || 'Invalid credentials')
                } else if (response.status >= 500) {
                    throw new Error('Server error. Please try again later.')
                } else {
                    throw new Error(data.detail || `Authentication failed (${response.status})`)
                }
            }

            const data = await response.json()

            // Store token
            token.value = data.access_token || data.token
            localStorage.setItem('auth_token', token.value)
            localStorage.setItem('auth_user', username)

            // Fetch user profile
            await refreshMe()

            return { success: true }
        } catch (e) {
            error.value = e.message
            return { success: false, error: e.message }
        } finally {
            loading.value = false
        }
    }

    async function refreshMe() {
        if (!token.value) return

        try {
            const response = await fetch(`${API_BASE}/auth/me`, {
                headers: {
                    'Authorization': `Bearer ${token.value}`
                }
            })

            if (response.ok) {
                const data = await response.json()
                user.value = data.user || data
                orgContext.value = data.organization || data.org_context || null
                roles.value = data.roles || []
            } else if (response.status === 401) {
                // Token expired or invalid
                logout()
            }
        } catch (e) {
            console.warn('Failed to refresh user profile:', e.message)
        }
    }

    function logout() {
        token.value = null
        user.value = null
        orgContext.value = null
        roles.value = []
        localStorage.removeItem('auth_token')
        localStorage.removeItem('auth_user')
    }

    // Initialize on store creation
    if (token.value) {
        refreshMe()
    }

    return {
        // State
        token,
        user,
        orgContext,
        roles,
        loading,
        error,
        // Computed
        isAuthenticated,
        userInitials,
        userDisplayName,
        // Actions
        login,
        logout,
        refreshMe
    }
})
