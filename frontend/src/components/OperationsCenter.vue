<script setup>
/**
 * Operations Center - Unified Fleet & Training Operations
 *
 * Consolidates: Fleets & Devices, Training Monitor, TGSP Marketplace, Integrations
 * Real-time operations monitoring and fleet management
 */
import { ref, onMounted } from 'vue'
import {
    Server, Radio, Package, Link, RefreshCw, Plus
} from 'lucide-vue-next'
import TrainingMonitor from './TrainingMonitor.vue'
import TGSPMarketplace from './TGSPMarketplace.vue'
import IntegrationsHub from './IntegrationsHub.vue'

const props = defineProps({
    initialTab: { type: String, default: 'fleets' }
})

const activeTab = ref(props.initialTab)

const tabs = [
    { id: 'fleets', label: 'Fleet Management', icon: Server },
    { id: 'monitor', label: 'Training Monitor', icon: Radio },
    { id: 'packages', label: 'TGSP Packages', icon: Package },
    { id: 'integrations', label: 'Integrations', icon: Link }
]

// Fleet data
const fleets = ref([])
const loading = ref(true)
const fleetError = ref('')

const fetchFleets = async () => {
    loading.value = true
    fleetError.value = ''
    try {
        const res = await fetch('/api/v1/fleets/extended')
        if (res.ok) {
            fleets.value = await res.json()
        } else {
            const err = await res.json()
            fleetError.value = err.detail || 'Failed to load fleet data.'
            fleets.value = []
        }
    } catch (e) {
        fleetError.value = 'Unable to reach fleet APIs. Check backend connectivity.'
        fleets.value = []
    }
    loading.value = false
}

const getStatusColor = (status) => {
    const colors = { Healthy: 'text-green-500', Degraded: 'text-yellow-500', Critical: 'text-red-500' }
    return colors[status] || 'text-gray-500'
}

onMounted(() => {
    fetchFleets()
})
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Header with Tabs -->
    <div class="flex-shrink-0 border-b border-[#30363d] bg-[#0d1117]">
      <div class="px-6 pt-4">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h1 class="text-xl font-bold text-white">Operations</h1>
            <p class="text-xs text-gray-500">Fleet management, training, and deployments</p>
          </div>
          <button @click="fetchFleets" class="p-2 rounded hover:bg-[#1f2428] transition-colors">
            <RefreshCw class="w-4 h-4 text-gray-400" :class="loading ? 'animate-spin' : ''" />
          </button>
        </div>

        <div class="flex gap-1">
          <button v-for="tab in tabs" :key="tab.id"
                  @click="activeTab = tab.id"
                  :class="['px-4 py-2.5 rounded-t-lg flex items-center gap-2 transition-colors text-sm font-medium',
                           activeTab === tab.id
                             ? 'bg-[#161b22] text-white border-t border-x border-[#30363d]'
                             : 'text-gray-400 hover:text-white hover:bg-[#161b22]/50']">
            <component :is="tab.icon" class="w-4 h-4" />
            {{ tab.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- Tab Content -->
    <div class="flex-1 overflow-hidden bg-[#161b22]">
      <!-- Fleets Tab -->
      <div v-if="activeTab === 'fleets'" class="h-full overflow-y-auto p-6">
        <div class="flex items-center justify-between mb-6">
          <div class="flex items-center gap-4">
            <div class="bg-[#0d1117] border border-[#30363d] rounded-lg px-4 py-2">
              <span class="text-2xl font-bold text-white">{{ fleets.length }}</span>
              <span class="text-xs text-gray-500 ml-2">fleets</span>
            </div>
            <div class="bg-[#0d1117] border border-[#30363d] rounded-lg px-4 py-2">
              <span class="text-2xl font-bold text-green-500">{{ fleets.reduce((sum, f) => sum + f.devices_online, 0) }}</span>
              <span class="text-xs text-gray-500 ml-2">devices online</span>
            </div>
          </div>
          <button class="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium flex items-center gap-2">
            <Plus class="w-4 h-4" /> Add Fleet
          </button>
        </div>

        <div v-if="fleetError" class="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200 mb-4">
          {{ fleetError }}
        </div>

        <div class="space-y-4">
          <div v-for="fleet in fleets" :key="fleet.id"
               class="bg-[#0d1117] border border-[#30363d] rounded-lg p-5 hover:border-[#484f58] transition-colors">
            <div class="flex items-start justify-between mb-4">
              <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-lg bg-[#1f2428] border border-[#30363d] flex items-center justify-center">
                  <Server class="w-6 h-6 text-gray-400" />
                </div>
                <div>
                  <h3 class="font-semibold text-white">{{ fleet.name }}</h3>
                  <div class="flex items-center gap-2 text-xs text-gray-500">
                    <span>{{ fleet.region }}</span>
                    <span>•</span>
                    <span :class="getStatusColor(fleet.status)">{{ fleet.status }}</span>
                  </div>
                </div>
              </div>
              <div class="text-right">
                <div class="text-2xl font-bold text-white">{{ fleet.trust }}%</div>
                <div class="text-xs text-gray-500">Trust Score</div>
              </div>
            </div>

            <div class="grid grid-cols-3 gap-4">
              <div class="bg-[#161b22] p-3 rounded border border-[#30363d]">
                <div class="text-xs text-gray-500">Total Devices</div>
                <div class="text-lg font-bold text-white">{{ fleet.devices_total }}</div>
              </div>
              <div class="bg-[#161b22] p-3 rounded border border-[#30363d]">
                <div class="text-xs text-gray-500">Online</div>
                <div class="text-lg font-bold text-green-500">{{ fleet.devices_online }}</div>
              </div>
              <div class="bg-[#161b22] p-3 rounded border border-[#30363d]">
                <div class="text-xs text-gray-500">Utilization</div>
                <div class="text-lg font-bold text-blue-500">
                  {{ fleet.devices_total ? ((fleet.devices_online / fleet.devices_total) * 100).toFixed(0) : 0 }}%
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Training Monitor Tab -->
      <div v-else-if="activeTab === 'monitor'" class="h-full overflow-y-auto p-6">
        <TrainingMonitor />
      </div>

      <!-- Packages Tab -->
      <div v-else-if="activeTab === 'packages'" class="h-full overflow-y-auto p-6">
        <TGSPMarketplace />
      </div>

      <!-- Integrations Tab -->
      <div v-else-if="activeTab === 'integrations'" class="h-full overflow-y-auto p-6">
        <IntegrationsHub />
      </div>
    </div>
  </div>
</template>
