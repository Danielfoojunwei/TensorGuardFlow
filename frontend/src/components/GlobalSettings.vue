<script setup>
import { Settings, Shield, Lock, Globe, Check, Loader2, Eye, EyeOff } from 'lucide-vue-next'
import { ref, onMounted } from 'vue'
import { settingsApi } from '../services/api'
import { useDemoModeStore } from '../stores/demoMode'
import { useToastStore } from '../stores/toast'

const demoMode = useDemoModeStore()
const toast = useToastStore()

const config = ref({
    kms: { provider: 'local', resource_id: '' },
    rtpl: { mode: 'front', profile: 'collaborative' },
    pqc: { n2he: true, dsa: true }
})

const saving = ref(false)
const saved = ref(false)
const loading = ref(true)

// Load settings from backend on mount
onMounted(async () => {
    try {
        const data = await settingsApi.getSettings()
        if (data.kms_provider) config.value.kms.provider = data.kms_provider
        if (data.rtpl_mode) config.value.rtpl.mode = data.rtpl_mode
        if (data.n2he_enabled !== undefined) config.value.pqc.n2he = data.n2he_enabled === true || data.n2he_enabled === 'true'
        if (data.dsa_enabled !== undefined) config.value.pqc.dsa = data.dsa_enabled === true || data.dsa_enabled === 'true'
    } catch (e) {
        console.warn("Failed to load settings", e)
    }
    loading.value = false
})

// Save settings to backend
const saveSettings = async () => {
    saving.value = true
    saved.value = false
    try {
        await settingsApi.bulkUpdate([
            { key: 'kms_provider', value: config.value.kms.provider },
            { key: 'rtpl_mode', value: config.value.rtpl.mode },
            { key: 'n2he_enabled', value: String(config.value.pqc.n2he) },
            { key: 'dsa_enabled', value: String(config.value.pqc.dsa) }
        ])
        saved.value = true
        toast.success('Settings saved successfully')
        setTimeout(() => { saved.value = false }, 2000)
    } catch (e) {
        console.error("Failed to save settings", e)
        toast.error('Failed to save settings: ' + e.message)
    }
    saving.value = false
}

const toggleDemoMode = () => {
    demoMode.toggle()
    if (demoMode.isEnabled) {
        toast.info('Demo mode enabled - data shown is simulated')
    } else {
        toast.info('Demo mode disabled - showing real data')
    }
}
</script>

<template>
  <div class="h-full overflow-y-auto">
    <div class="max-w-4xl mx-auto p-6 space-y-6">
      <div class="flex items-center justify-between">
         <div>
           <h2 class="text-2xl font-bold text-white">Global Settings</h2>
           <span class="text-xs text-gray-500">System Configuration & Policy</span>
         </div>
         <button @click="saveSettings" :disabled="saving" class="btn btn-primary flex items-center gap-2" data-testid="save-settings">
            <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
            <Check v-else-if="saved" class="w-4 h-4" />
            {{ saving ? 'Saving...' : (saved ? 'Saved!' : 'Save Changes') }}
         </button>
      </div>

      <!-- Demo Mode Section -->
      <div class="bg-yellow-500/5 border border-yellow-500/30 p-6 rounded-lg">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg bg-yellow-500/20 flex items-center justify-center">
              <component :is="demoMode.isEnabled ? Eye : EyeOff" class="w-5 h-5 text-yellow-500" />
            </div>
            <div>
              <h3 class="font-bold text-white">Demo Mode</h3>
              <p class="text-xs text-gray-500">When enabled, the system displays simulated data for demonstration purposes.</p>
            </div>
          </div>
          <div class="flex items-center gap-4">
            <span :class="['text-sm font-medium', demoMode.isEnabled ? 'text-yellow-500' : 'text-gray-500']">
              {{ demoMode.isEnabled ? 'ENABLED' : 'DISABLED' }}
            </span>
            <button
              @click="toggleDemoMode"
              data-testid="demo-mode-toggle"
              :class="[
                'w-12 h-6 rounded-full relative transition-colors',
                demoMode.isEnabled ? 'bg-yellow-500' : 'bg-[#333]'
              ]"
              role="switch"
              :aria-checked="demoMode.isEnabled"
            >
              <div :class="[
                'w-5 h-5 bg-white rounded-full absolute top-0.5 transition-all',
                demoMode.isEnabled ? 'left-[26px]' : 'left-0.5'
              ]"></div>
            </button>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-6">
          <!-- KMS Provider -->
          <div class="bg-[#0d1117] border border-[#30363d] p-6 rounded-lg">
             <div class="flex items-center gap-2 mb-4">
                <Lock class="w-5 h-5 text-gray-400" />
                <h3 class="font-bold text-white">KMS Provider Strategy</h3>
             </div>

             <div class="space-y-4">
                <label class="flex items-center gap-3 p-3 border border-[#30363d] rounded cursor-pointer hover:bg-[#161b22]"
                       :class="config.kms.provider === 'local' ? 'border-orange-500 bg-orange-500/5' : ''">
                   <input type="radio" v-model="config.kms.provider" value="local" class="accent-orange-500">
                   <div>
                      <div class="font-bold text-sm text-white">Local Hardware Security Module</div>
                      <div class="text-xs text-gray-500">Use on-prem HSM for master key wrapping</div>
                   </div>
                </label>

                <label class="flex items-center gap-3 p-3 border border-[#30363d] rounded cursor-pointer hover:bg-[#161b22]"
                       :class="config.kms.provider === 'aws' ? 'border-orange-500 bg-orange-500/5' : ''">
                   <input type="radio" v-model="config.kms.provider" value="aws" class="accent-orange-500">
                   <div>
                      <div class="font-bold text-sm text-white">AWS KMS (Cloud Bridge)</div>
                      <div class="text-xs text-gray-500">Delegate to AWS KMS via TEE Enclave</div>
                   </div>
                </label>
             </div>
          </div>

          <!-- RTPL Privacy -->
          <div class="bg-[#0d1117] border border-[#30363d] p-6 rounded-lg">
             <div class="flex items-center gap-2 mb-4">
                <Shield class="w-5 h-5 text-gray-400" />
                <h3 class="font-bold text-white">RTPL Privacy Mode</h3>
             </div>

             <select v-model="config.rtpl.mode" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white mb-4">
                 <option value="front">Front-Running Obfuscation (Fast)</option>
                 <option value="onion">Onion Routing (Secure)</option>
                 <option value="chaff">Chaff Injection (Extreme)</option>
             </select>

             <div class="p-3 bg-[#1f2428] rounded text-xs text-gray-400 border border-[#30363d]">
                 Current mode adds <span class="text-white font-bold">~12ms</span> latency per inference to guarantee <span class="text-white font-bold">k-anonymity=5</span>.
             </div>
          </div>

          <!-- PQC Verification Toggles -->
          <div class="bg-[#0d1117] border border-[#30363d] p-6 rounded-lg col-span-2">
              <div class="flex items-center gap-2 mb-4">
                  <Shield class="w-5 h-5 text-green-500" />
                  <h3 class="font-bold text-white">Internally Verified PQC (v2.4 GA)</h3>
              </div>

              <div class="grid grid-cols-2 gap-4">
                  <div class="flex items-center justify-between p-4 bg-[#161b22] border border-[#30363d] rounded-lg">
                      <div>
                          <div class="text-sm font-bold text-white">N2HE Lattice Encryption</div>
                          <div class="text-[11px] text-gray-500">Recycles DP noise for 90% overhead reduction.</div>
                      </div>
                      <div class="w-10 h-5 rounded-full relative transition-colors cursor-pointer"
                           :class="config.pqc.n2he ? 'bg-primary' : 'bg-[#333]'"
                           @click="config.pqc.n2he = !config.pqc.n2he"
                           role="switch"
                           :aria-checked="config.pqc.n2he"
                           tabindex="0"
                           @keydown.enter="config.pqc.n2he = !config.pqc.n2he"
                           @keydown.space.prevent="config.pqc.n2he = !config.pqc.n2he">
                          <div class="w-4 h-4 bg-white rounded-full absolute top-0.5 transition-all" :style="config.pqc.n2he ? 'left: 22px' : 'left: 2px'"></div>
                      </div>
                  </div>

                  <div class="flex items-center justify-between p-4 bg-[#161b22] border border-[#30363d] rounded-lg">
                      <div>
                          <div class="text-sm font-bold text-white">Dilithium-3 Signatures</div>
                          <div class="text-[11px] text-gray-500">Post-quantum tamper-evident evidence fabric.</div>
                      </div>
                      <div class="w-10 h-5 rounded-full relative transition-colors cursor-pointer"
                           :class="config.pqc.dsa ? 'bg-primary' : 'bg-[#333]'"
                           @click="config.pqc.dsa = !config.pqc.dsa"
                           role="switch"
                           :aria-checked="config.pqc.dsa"
                           tabindex="0"
                           @keydown.enter="config.pqc.dsa = !config.pqc.dsa"
                           @keydown.space.prevent="config.pqc.dsa = !config.pqc.dsa">
                          <div class="w-4 h-4 bg-white rounded-full absolute top-0.5 transition-all" :style="config.pqc.dsa ? 'left: 22px' : 'left: 2px'"></div>
                      </div>
                  </div>
              </div>
          </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.btn {
  @apply px-4 py-2 rounded font-medium transition-colors duration-200 flex items-center inline-flex;
}
.btn-primary {
  @apply bg-orange-600 text-white hover:bg-orange-700;
}
</style>
