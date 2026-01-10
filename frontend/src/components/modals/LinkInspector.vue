<script setup>
import { ref } from 'vue'
import { X, Network, Lock, Sliders, Activity } from 'lucide-vue-next'

const props = defineProps(['edge'])
const emit = defineEmits(['close', 'update'])

const config = ref({
  compression: 'zstd',
  bandwidthLimit: 100,
  privacyBudget: 3.5,
  encryption: 'AES-256-GCM'
})

const save = () => {
  emit('update', { id: props.edge.id, config: config.value })
  emit('close')
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm" @click.self="$emit('close')">
    <div class="bg-[#111] border border-[#333] rounded-xl shadow-2xl w-[500px] flex flex-col overflow-hidden">
      <!-- Header -->
      <div class="p-4 border-b border-[#333] flex justify-between items-center bg-[#161b22]">
        <div class="flex items-center gap-2">
           <Network class="w-5 h-5 text-primary" />
           <div>
             <h3 class="font-bold text-white">Link Configuration</h3>
             <div class="text-xs text-gray-500 font-mono">{{ edge.source }} <span class="text-primary">--></span> {{ edge.target }}</div>
           </div>
        </div>
        <button @click="$emit('close')" class="text-gray-500 hover:text-white"><X class="w-5 h-5" /></button>
      </div>

      <!-- Body -->
      <div class="p-6 space-y-6">
         <!-- Privacy Budget -->
         <div class="space-y-2">
            <div class="flex justify-between">
                <label class="text-sm font-bold text-gray-400 flex items-center gap-2">
                    <Lock class="w-3 h-3" /> Privacy Budget (ε)
                </label>
                <span class="font-mono text-primary font-bold">{{ config.privacyBudget }}</span>
            </div>
            <input type="range" min="0.1" max="10" step="0.1" v-model="config.privacyBudget" class="w-full accent-primary h-1 bg-[#333] rounded-lg appearance-none cursor-pointer">
            <div class="text-[10px] text-gray-500">Lower ε guarantees stronger privacy but adds more noise.</div>
         </div>

         <!-- Compression -->
         <div class="space-y-2">
            <label class="text-sm font-bold text-gray-400 flex items-center gap-2">
                <Sliders class="w-3 h-3" /> Compression Algo
            </label>
            <div class="grid grid-cols-3 gap-2">
                <button v-for="algo in ['none', 'zstd', 'lz4']" :key="algo"
                        @click="config.compression = algo"
                        class="px-3 py-2 border rounded text-xs font-mono uppercase transition-colors"
                        :class="config.compression === algo ? 'border-primary bg-primary/10 text-primary' : 'border-[#333] text-gray-500 hover:border-gray-400'">
                    {{ algo }}
                </button>
            </div>
         </div>

         <!-- QoS -->
         <div class="space-y-2">
             <label class="text-sm font-bold text-gray-400 flex items-center gap-2">
                <Activity class="w-3 h-3" /> Bandwidth Cap
             </label>
             <div class="flex items-center gap-2">
                 <input type="number" v-model="config.bandwidthLimit" class="bg-[#050505] border border-[#333] rounded p-2 text-sm text-white w-24">
                 <span class="text-xs text-gray-500">Mbps</span>
             </div>
         </div>
      </div>

      <!-- Footer -->
      <div class="p-4 border-t border-[#333] bg-[#161b22] flex justify-end gap-3">
          <button @click="$emit('close')" class="px-4 py-2 rounded text-sm text-gray-400 hover:text-white">Cancel</button>
          <button @click="save" class="px-4 py-2 bg-primary text-black font-bold rounded hover:bg-orange-600 transition-colors">Apply Config</button>
      </div>
    </div>
  </div>
</template>
