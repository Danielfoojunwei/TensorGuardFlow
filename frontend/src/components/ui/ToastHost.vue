<script setup>
import { useToastStore } from '../../stores/toast'
import { CheckCircle, AlertCircle, AlertTriangle, Info, X } from 'lucide-vue-next'

const toastStore = useToastStore()

const getIcon = (type) => {
    const icons = {
        success: CheckCircle,
        error: AlertCircle,
        warning: AlertTriangle,
        info: Info
    }
    return icons[type] || Info
}

const getStyles = (type) => {
    const styles = {
        success: {
            bg: 'bg-green-500/10',
            border: 'border-green-500/30',
            icon: 'text-green-500',
            text: 'text-green-100'
        },
        error: {
            bg: 'bg-red-500/10',
            border: 'border-red-500/30',
            icon: 'text-red-500',
            text: 'text-red-100'
        },
        warning: {
            bg: 'bg-yellow-500/10',
            border: 'border-yellow-500/30',
            icon: 'text-yellow-500',
            text: 'text-yellow-100'
        },
        info: {
            bg: 'bg-blue-500/10',
            border: 'border-blue-500/30',
            icon: 'text-blue-500',
            text: 'text-blue-100'
        }
    }
    return styles[type] || styles.info
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 max-w-md pointer-events-none">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toastStore.toasts"
          :key="toast.id"
          :class="[
            'flex items-start gap-3 p-4 rounded-lg border backdrop-blur-sm shadow-xl pointer-events-auto',
            'animate-in fade-in slide-in-from-right-4 duration-300',
            getStyles(toast.type).bg,
            getStyles(toast.type).border
          ]"
          role="alert"
          :aria-live="toast.type === 'error' ? 'assertive' : 'polite'"
        >
          <component
            :is="getIcon(toast.type)"
            :class="['w-5 h-5 flex-shrink-0', getStyles(toast.type).icon]"
          />
          <p :class="['text-sm flex-1', getStyles(toast.type).text]">
            {{ toast.message }}
          </p>
          <button
            @click="toastStore.removeToast(toast.id)"
            class="text-gray-500 hover:text-white transition-colors p-0.5"
            aria-label="Dismiss notification"
          >
            <X class="w-4 h-4" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
