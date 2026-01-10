<script setup>
import { Server, Radio, MoreVertical, Plus } from 'lucide-vue-next'

const fleets = [
  { id: 'f1', name: 'US-East-1 Cluster', region: 'us-east-1', status: 'Healthy', devices_total: 450, devices_online: 442, trust: 99.2 },
  { id: 'f2', name: 'Berlin Gigafactory', region: 'eu-central-1', status: 'Degraded', devices_total: 120, devices_online: 89, trust: 84.5 },
]
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
       <div>
         <h2 class="text-2xl font-bold">Fleets & Devices</h2>
         <span class="text-xs text-gray-500">Edge Node Orchestration</span>
       </div>
       <button class="btn btn-primary">
          <Plus class="w-4 h-4 mr-2" /> Enroll New Device
       </button>
    </div>

    <div class="grid grid-cols-1 gap-4">
       <div v-for="fleet in fleets" :key="fleet.id" class="bg-[#0d1117] border border-[#30363d] rounded-lg p-6 relative overflow-hidden group hover:border-[#58a6ff] transition-colors">
          <div class="flex items-start justify-between mb-6">
             <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded bg-[#1f2428] border border-[#30363d] flex items-center justify-center">
                    <Server class="w-6 h-6 text-gray-400" />
                </div>
                <div>
                   <h3 class="font-bold text-lg">{{ fleet.name }}</h3>
                   <div class="flex items-center gap-2 text-xs text-gray-500">
                      <span>{{ fleet.region }}</span>
                      <span>•</span>
                      <span :class="fleet.status === 'Healthy' ? 'text-green-500' : 'text-yellow-500'">{{ fleet.status }}</span>
                   </div>
                </div>
             </div>
             
             <div class="text-right">
                <div class="text-2xl font-bold">{{ fleet.trust }}%</div>
                <div class="text-xs text-gray-500">Trust Score</div>
             </div>
          </div>
          
          <div class="grid grid-cols-2 gap-4">
             <div class="bg-[#161b22] p-3 rounded border border-[#30363d] flex items-center justify-between">
                 <span class="text-sm text-gray-400">Total Devices</span>
                 <span class="font-mono font-bold">{{ fleet.devices_total }}</span>
             </div>
             <div class="bg-[#161b22] p-3 rounded border border-[#30363d] flex items-center justify-between">
                 <span class="text-sm text-gray-400">Online</span>
                 <span class="font-mono font-bold text-green-500">{{ fleet.devices_online }}</span>
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
