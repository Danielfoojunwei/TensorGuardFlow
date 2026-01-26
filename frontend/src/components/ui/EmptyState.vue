<script setup>
/**
 * Empty State Component
 *
 * Provides clear guidance when no data is available
 */
import { Inbox, Plus } from 'lucide-vue-next'

const props = defineProps({
    icon: {
        type: Object,
        default: () => Inbox
    },
    title: {
        type: String,
        default: 'No data yet'
    },
    description: {
        type: String,
        default: 'Get started by creating your first item.'
    },
    actionLabel: {
        type: String,
        default: null
    }
})

const emit = defineEmits(['action'])
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 px-4 text-center">
    <div class="w-16 h-16 rounded-full bg-[#1f2428] flex items-center justify-center mb-4">
      <component :is="icon" class="w-8 h-8 text-gray-500" />
    </div>
    <h3 class="text-lg font-semibold text-white mb-2">{{ title }}</h3>
    <p class="text-sm text-gray-500 max-w-sm mb-6">{{ description }}</p>
    <button
      v-if="actionLabel"
      @click="emit('action')"
      class="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium flex items-center gap-2 transition-colors"
    >
      <Plus class="w-4 h-4" />
      {{ actionLabel }}
    </button>
    <slot></slot>
  </div>
</template>
