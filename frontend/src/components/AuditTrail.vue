<script setup>
import { ClipboardList, Hash, RefreshCw, FileText } from 'lucide-vue-next'
import { ref, onMounted } from 'vue'

const auditLogs = ref([])
const loading = ref(false)

const fetchLogs = async () => {
    loading.value = true
    try {
        const res = await fetch('/api/v1/audit/logs?limit=50')
        if (res.ok) {
            const data = await res.json()
            auditLogs.value = data
        } else {
            throw new Error('Backend not available')
        }
    } catch (e) {
        console.warn("Failed to fetch audit logs - using fallback data", e)
        // Fallback to mock data if backend not available
        auditLogs.value = [
            { id: 'ev-1', action: 'KEY_ROTATION_SUCCESS', actor: 'SYSTEM', target: 'key-us-east-1', hash: 'e3b0c44298fc1...2427ae41e4649', time: '10m ago' },
            { id: 'ev-2', action: 'MODEL_DEPLOY', actor: 'Daniel Foo', target: 'llama-3-8b-finetuned-v2', hash: '8f434346648f6...1dd3c1ac88b59', time: '1h ago' },
            { id: 'ev-3', action: 'FLEET_ENROLL', actor: 'PROVISIONER', target: 'device-ax-99', hash: 'ca978112ca1bb...807785afee48bb', time: '2h ago' },
        ]
    }
    loading.value = false
}

const syncRecords = () => fetchLogs()

onMounted(fetchLogs)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
       <div>
         <h2 class="text-2xl font-bold">Immutable Audit Trail</h2>
         <span class="text-xs text-gray-500">Cryptographic Traceability</span>
       </div>
       <button @click="syncRecords" class="btn btn-secondary">
          <RefreshCw class="w-4 h-4 mr-2" :class="loading ? 'animate-spin' : ''" /> Sync Records
       </button>
    </div>

    <div class="bg-[#0d1117] border border-[#30363d] rounded-lg overflow-hidden">
       <div v-if="auditLogs.length === 0" class="flex flex-col items-center justify-center p-20 text-gray-500">
           <ClipboardList class="w-16 h-16 mb-4 opacity-20" />
           <p>No security events found</p>
       </div>
       
       <div v-else class="divide-y divide-[#30363d]">
          <div v-for="log in auditLogs" :key="log.id" class="p-4 hover:bg-[#161b22] transition-colors flex items-center justify-between group">
             <div class="flex items-center gap-4">
                <div class="p-2 bg-[#1f2428] rounded border border-[#30363d] text-gray-400">
                    <Hash class="w-5 h-5" />
                </div>
                <div>
                   <div class="flex items-center gap-2">
                      <span class="font-bold text-sm">{{ log.action }}</span>
                      <span class="bg-gray-800 text-gray-400 text-[10px] px-1.5 rounded font-mono">{{ log.time }}</span>
                   </div>
                   <div class="text-xs text-gray-500 font-mono mt-0.5 max-w-md truncate">HASH: {{ log.hash }}</div>
                </div>
             </div>
             
             <div class="text-right text-sm">
                <div class="text-gray-300">By <span class="font-bold text-white">{{ log.actor }}</span></div>
                <div class="text-xs text-gray-500">Target: {{ log.target }}</div>
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
.btn-secondary {
  @apply border border-[#30363d] text-gray-300 hover:text-white hover:bg-[#161b22];
}
</style>
