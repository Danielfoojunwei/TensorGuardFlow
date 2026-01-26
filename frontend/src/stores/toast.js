/**
 * Toast Store - Global Notification System
 *
 * Provides:
 * - Success/error/warning/info notifications
 * - Auto-dismiss with configurable duration
 * - Queue management for multiple toasts
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useToastStore = defineStore('toast', () => {
    const toasts = ref([])
    let idCounter = 0

    function addToast(message, type = 'info', duration = 5000) {
        const id = ++idCounter
        toasts.value.push({
            id,
            message,
            type,
            createdAt: Date.now()
        })

        // Auto-dismiss
        if (duration > 0) {
            setTimeout(() => {
                removeToast(id)
            }, duration)
        }

        return id
    }

    function removeToast(id) {
        const index = toasts.value.findIndex(t => t.id === id)
        if (index > -1) {
            toasts.value.splice(index, 1)
        }
    }

    function clearAll() {
        toasts.value = []
    }

    // Convenience methods
    function success(message, duration = 5000) {
        return addToast(message, 'success', duration)
    }

    function error(message, duration = 8000) {
        return addToast(message, 'error', duration)
    }

    function warning(message, duration = 6000) {
        return addToast(message, 'warning', duration)
    }

    function info(message, duration = 5000) {
        return addToast(message, 'info', duration)
    }

    return {
        toasts,
        addToast,
        removeToast,
        clearAll,
        success,
        error,
        warning,
        info
    }
})

// Helper functions for direct import usage
export function notifySuccess(message, duration) {
    const store = useToastStore()
    return store.success(message, duration)
}

export function notifyError(message, duration) {
    const store = useToastStore()
    return store.error(message, duration)
}

export function notifyWarning(message, duration) {
    const store = useToastStore()
    return store.warning(message, duration)
}

export function notifyInfo(message, duration) {
    const store = useToastStore()
    return store.info(message, duration)
}
