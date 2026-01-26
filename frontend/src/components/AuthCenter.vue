<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import {
    Shield, Mail, Lock, LogIn, Github,
    Chrome, MessageSquare, AlertCircle, ChevronRight
} from 'lucide-vue-next'

const router = useRouter()
const sessionStore = useSessionStore()

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
    if (!email.value || !password.value) {
        error.value = 'Please provide both email and password.'
        return
    }

    loading.value = true
    error.value = ''

    try {
        const result = await sessionStore.login(email.value, password.value)

        if (result.success) {
            // Check for redirect path
            const redirectPath = sessionStorage.getItem('auth_redirect')
            sessionStorage.removeItem('auth_redirect')
            router.push(redirectPath || '/dashboard')
        } else {
            error.value = result.error || 'Authentication failed'
        }
    } catch (e) {
        error.value = e.message || 'An unexpected error occurred'
    } finally {
        loading.value = false
    }
}

const handleOAuth = (provider) => {
    alert(`OAuth with ${provider} is not yet configured. Please use email/password login.`)
}
</script>

<template>
  <div class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-[#050505] overflow-hidden">
    <!-- Animated Background Elements -->
    <div class="absolute inset-0 overflow-hidden">
        <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/10 blur-[120px] rounded-full animate-pulse"></div>
        <div class="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/10 blur-[120px] rounded-full animate-pulse decoration-delay-2000"></div>
    </div>

    <div class="w-full max-w-[440px] relative">
      <!-- Logo & Branding -->
      <div class="text-center mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500 to-orange-400 p-0.5 mb-4 shadow-lg shadow-orange-500/20">
            <div class="w-full h-full bg-[#0d1117] rounded-[14px] flex items-center justify-center">
                <Shield class="w-8 h-8 text-orange-500" />
            </div>
        </div>
        <h1 class="text-2xl font-bold tracking-tight text-orange-500 mb-1">DYNAMICAL</h1>
        <p class="text-xs text-gray-500 uppercase font-bold tracking-widest">Enterprise Access Hub • v2.4 GA</p>
      </div>

      <!-- Login Card (Glassmorphism) -->
      <div class="bg-[#0d1117]/80 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl animate-in fade-in zoom-in duration-500 delay-200">
        <div v-if="error" class="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-3 animate-in fade-in slide-in-from-top-2">
            <AlertCircle class="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
            <p class="text-xs text-red-400 font-medium leading-relaxed">{{ error }}</p>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-5" data-testid="login-form">
          <div class="space-y-1.5">
            <label class="text-[10px] font-bold text-gray-400 uppercase ml-1">Work Email</label>
            <div class="relative group">
              <Mail class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 group-focus-within:text-primary transition-colors" />
              <input
                v-model="email"
                type="email"
                placeholder="name@company.com"
                data-testid="login-email"
                autocomplete="username"
                class="w-full bg-black/40 border border-white/10 rounded-xl pl-10 pr-4 py-3 text-sm text-white placeholder:text-gray-700 focus:border-primary/50 focus:ring-4 focus:ring-primary/5 outline-none transition-all"
              />
            </div>
          </div>

          <div class="space-y-1.5">
            <div class="flex items-center justify-between ml-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase">Password</label>
                <button type="button" class="text-[10px] font-bold text-primary hover:text-primary/80 uppercase">Reset</button>
            </div>
            <div class="relative group">
              <Lock class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600 group-focus-within:text-primary transition-colors" />
              <input
                v-model="password"
                type="password"
                placeholder="••••••••"
                data-testid="login-password"
                autocomplete="current-password"
                class="w-full bg-black/40 border border-white/10 rounded-xl pl-10 pr-4 py-3 text-sm text-white placeholder:text-gray-700 focus:border-primary/50 focus:ring-4 focus:ring-primary/5 outline-none transition-all"
              />
            </div>
          </div>

          <button
            type="submit"
            :disabled="loading"
            data-testid="login-submit"
            class="w-full bg-primary hover:bg-primary/90 text-white font-bold h-12 rounded-xl flex items-center justify-center gap-2 transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed group shadow-lg shadow-primary/10"
          >
            <span v-if="!loading">Authorize Access</span>
            <span v-else class="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            <ChevronRight v-if="!loading" class="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
        </form>

        <!-- Divider -->
        <div class="my-8 flex items-center gap-4">
            <div class="h-px flex-1 bg-white/5"></div>
            <span class="text-[9px] font-bold text-gray-600 uppercase tracking-widest whitespace-nowrap">Corporate SSO</span>
            <div class="h-px flex-1 bg-white/5"></div>
        </div>

        <!-- OAuth Options -->
        <div class="grid grid-cols-2 gap-3">
            <button @click="handleOAuth('GitHub')" class="flex items-center justify-center gap-2 h-11 rounded-xl bg-white/5 border border-white/10 text-xs font-bold text-white hover:bg-white/10 transition-all">
                <Github class="w-4 h-4" /> GitHub
            </button>
            <button @click="handleOAuth('Google')" class="flex items-center justify-center gap-2 h-11 rounded-xl bg-white/5 border border-white/10 text-xs font-bold text-white hover:bg-white/10 transition-all">
                <Chrome class="w-4 h-4" /> Google
            </button>
        </div>
      </div>

      <!-- Security Notice -->
      <div class="mt-8 text-center animate-in fade-in duration-1000 delay-700">
        <p class="text-[10px] text-gray-500 leading-relaxed uppercase tracking-tight">
          By continuing, you agree to the <span class="text-gray-400">Security Access Policy</span>.<br/>
          Unauthorized access attempts are logged and reported via Dilithium-3 signatures.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-pulse {
  animation: pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.1; }
  50% { opacity: 0.2; }
}

.decoration-delay-2000 {
    animation-delay: 2s;
}
</style>
