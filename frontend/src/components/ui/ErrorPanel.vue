<script setup>
/**
 * Error Panel Component
 *
 * Displays error messages with retry capability
 */
import { AlertCircle, RefreshCw } from 'lucide-vue-next'

const props = defineProps({
    message: {
        type: String,
        default: 'Something went wrong'
    },
    details: {
        type: String,
        default: null
    },
    correlationId: {
        type: String,
        default: null
    },
    canRetry: {
        type: Boolean,
        default: true
    },
    loading: {
        type: Boolean,
        default: false
    }
})

const emit = defineEmits(['retry'])
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 px-4 text-center">
    <div class="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
      <AlertCircle class="w-8 h-8 text-red-500" />
    </div>
    <h3 class="text-lg font-semibold text-red-400 mb-2">{{ message }}</h3>
    <p v-if="details" class="text-sm text-gray-500 max-w-sm mb-2">{{ details }}</p>
    <p v-if="correlationId" class="text-xs font-mono text-gray-600 mb-6">
      Correlation ID: {{ correlationId }}
    </p>
    <button
      v-if="canRetry"
      @click="emit('retry')"
      :disabled="loading"
      class="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
    >
      <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" />
      {{ loading ? 'Retrying...' : 'Try Again' }}
    </button>
    <slot></slot>
  </div>
</template>
