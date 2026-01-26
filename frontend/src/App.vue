<script setup>
import { computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Sidebar from './components/Sidebar.vue'
import Header from './components/Header.vue'
import ToastHost from './components/ui/ToastHost.vue'
import { useDemoModeStore } from './stores/demoMode'

const router = useRouter()
const route = useRoute()
const demoMode = useDemoModeStore()

// Compute active section from route
const activeSection = computed(() => {
    const path = route.path
    if (path.startsWith('/models')) return 'models'
    if (path.startsWith('/operations')) return 'operations'
    if (path.startsWith('/security')) return 'security'
    if (path.startsWith('/settings')) return 'settings'
    if (path.startsWith('/dashboard') || path === '/') return 'dashboard'
    return 'dashboard'
})

// Check if on login page
const isLoginPage = computed(() => route.name === 'login')

// Handle navigation from sidebar
const handleNavigate = (target) => {
    if (target === 'signout') {
        localStorage.removeItem('auth_token')
        localStorage.removeItem('auth_user')
        router.push('/login')
        return
    }

    // Navigate to the appropriate route
    const routes = {
        dashboard: '/dashboard',
        models: '/models/registry',
        operations: '/operations/fleets',
        security: '/security/overview',
        settings: '/settings'
    }

    if (typeof target === 'object') {
        // Handle deep navigation with tab
        const basePath = routes[target.page] || '/dashboard'
        if (target.tab) {
            router.push(`/${target.page}/${target.tab}`)
        } else {
            router.push(basePath)
        }
    } else {
        router.push(routes[target] || '/dashboard')
    }
}
</script>

<template>
  <div class="flex h-screen bg-background text-secondary overflow-hidden">
    <!-- Demo Mode Banner -->
    <div v-if="demoMode.isEnabled && !isLoginPage" class="fixed top-0 left-0 right-0 z-50 bg-yellow-500 text-black text-center text-xs font-bold py-1 px-4">
      DEMO MODE - Data shown is simulated for demonstration purposes
    </div>

    <!-- Login Page (full screen, no sidebar) -->
    <template v-if="isLoginPage">
      <RouterView />
    </template>

    <!-- Authenticated Layout -->
    <template v-else>
      <!-- Sidebar -->
      <Sidebar :activeTab="activeSection" @update:activeTab="handleNavigate" />

      <!-- Main Content -->
      <div :class="['flex-1 flex flex-col ml-64 transition-all duration-300', demoMode.isEnabled ? 'pt-6' : '']">
        <Header />

        <main class="flex-1 overflow-hidden relative">
          <transition name="fade" mode="out-in">
            <RouterView v-slot="{ Component }">
              <component :is="Component" @navigate="handleNavigate" />
            </RouterView>
          </transition>
        </main>
      </div>
    </template>

    <!-- Toast Notifications -->
    <ToastHost />
  </div>
</template>

<style>
.bg-app { background-color: #000000; }
.bg-card { background-color: #0d1117; }
.border-border { border-color: #30363d; }

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
