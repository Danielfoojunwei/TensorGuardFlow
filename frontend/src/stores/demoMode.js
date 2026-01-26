/**
 * Demo Mode Store
 *
 * Manages the demo mode state for the application:
 * - Toggle demo mode on/off
 * - Persist preference to localStorage
 * - Provides flag for components to check
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useDemoModeStore = defineStore('demoMode', () => {
    // State - persisted to localStorage
    const enabled = ref(localStorage.getItem('demo_mode') === 'true')

    // Computed
    const isEnabled = computed(() => enabled.value)

    // Actions
    function toggle() {
        enabled.value = !enabled.value
        localStorage.setItem('demo_mode', String(enabled.value))
    }

    function enable() {
        enabled.value = true
        localStorage.setItem('demo_mode', 'true')
    }

    function disable() {
        enabled.value = false
        localStorage.setItem('demo_mode', 'false')
    }

    return {
        enabled,
        isEnabled,
        toggle,
        enable,
        disable
    }
})
