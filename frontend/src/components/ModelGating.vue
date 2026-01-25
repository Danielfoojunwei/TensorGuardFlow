<script setup>
import { ref, onMounted } from 'vue'
import { Sliders, Shield, Zap, Check, Loader2, AlertCircle } from 'lucide-vue-next'

const props = defineProps({
    expert: { type: Object, required: true }
})

const emit = defineEmits(['updated'])

const config = ref({
    iosp_enabled: true,
    scene_parsing: 'active',
    instruction_align: 'high',
    routing_strategy: 'iosp-v2'
})

const saving = ref(false)
const saved = ref(false)

onMounted(() => {
    if (props.expert.gating_config) {
        config.value = { ...config.value, ...props.expert.gating_config }
    }
})

const saveGating = async () => {
    saving.value = true
    saved.value = false
    try {
        const token = localStorage.getItem('auth_token')
        const res = await fetch(`/api/v1/fedmoe/experts/${props.expert.id}/gating`, {
            method: 'PUT',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(config.value)
        })
        if (res.ok) {
            saved.value = true
            emit('updated', await res.json())
            setTimeout(() => { saved.value = false }, 2000)
        }
    } catch (e) {
        console.error("Failed to save gating config", e)
    }
    saving.value = false
}
</script>

<template>
  <div class="bg-[#0d1117] border border-[#30363d] rounded-lg overflow-hidden">
    <div class="px-5 py-4 border-b border-[#30363d] flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Sliders class="w-4 h-4 text-primary" />
        <h3 class="font-bold text-white">IOSP Gating Control</h3>
      </div>
      <button @click="saveGating" :disabled="saving" class="px-3 py-1.5 bg-primary text-white text-xs font-bold rounded hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2">
        <Loader2 v-if="saving" class="w-3 h-3 animate-spin" />
        <Check v-else-if="saved" class="w-3 h-3" />
        {{ saving ? 'Saving...' : (saved ? 'Applied' : 'Apply GA Policy') }}
      </button>
    </div>

    <div class="p-5 space-y-4">
      <div class="flex items-start gap-4 p-3 bg-blue-500/5 border border-blue-500/20 rounded-md">
        <Shield class="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
        <div>
          <div class="text-xs font-bold text-blue-400 uppercase tracking-wider">v2.3 GA Production Policy</div>
          <div class="text-[11px] text-gray-400 leading-relaxed mt-1">
            Instruction-Oriented Scene-Parsing (IOSP) prevents parameter interference between experts while maintaining 94%+ success rate.
          </div>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div class="space-y-1">
          <label class="text-[10px] font-bold text-gray-500 uppercase">Routing Strategy</label>
          <select v-model="config.routing_strategy" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-xs text-white">
            <option value="iosp-v2">IOSP v2 (Validated GA)</option>
            <option value="iosp-v1">IOSP v1 (Legacy)</option>
            <option value="top-k">Standard Top-K (Baseline)</option>
          </select>
        </div>
        
        <div class="space-y-1">
          <label class="text-[10px] font-bold text-gray-500 uppercase">Scene Sensitivity</label>
          <select v-model="config.scene_parsing" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-xs text-white">
            <option value="active">Active (High Precision)</option>
            <option value="passive">Passive (Zero Overhead)</option>
            <option value="disabled">Disabled</option>
          </select>
        </div>
      </div>

      <div class="flex items-center justify-between p-3 border border-[#30363d] rounded-md hover:bg-[#161b22] transition-colors cursor-pointer" @click="config.iosp_enabled = !config.iosp_enabled">
        <div class="flex items-center gap-3">
          <Zap class="w-4 h-4" :class="config.iosp_enabled ? 'text-yellow-500' : 'text-gray-500'" />
          <div>
            <div class="text-xs font-bold text-white">Task-Aware Activation</div>
            <div class="text-[10px] text-gray-500">Only trigger experts matching instruction intent.</div>
          </div>
        </div>
        <div class="w-8 h-4 rounded-full relative transition-colors" :class="config.iosp_enabled ? 'bg-primary' : 'bg-[#333]'">
          <div class="w-3 h-3 bg-white rounded-full absolute top-0.5 transition-all" :style="config.iosp_enabled ? 'left: 18px' : 'left: 2px'"></div>
        </div>
      </div>
    </div>
  </div>
</template>
