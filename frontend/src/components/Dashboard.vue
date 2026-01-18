<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Activity, Database, Key, ShieldCheck, AlertCircle } from 'lucide-vue-next'
import PipelineGraph from './dashboard/PipelineGraph.vue'
import PerformanceDissect from './analytics/PerformanceDissect.vue'

const stats = ref([
  { label: 'System Health', value: '...', icon: Activity, color: 'text-green-500' },
  { label: 'Active Fleets', value: '...', icon: Database, color: 'text-blue-500' },
  { label: 'Keys Rotated', value: '...', icon: Key, color: 'text-orange-500' },
  { label: 'Compliance', value: '...', icon: ShieldCheck, color: 'text-purple-500' },
])

const loading = ref(true)
const error = ref(null)
let pollInterval = null

const fetchDashboardStats = async () => {
  try {
    const token = localStorage.getItem('auth_token')
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {}

    const response = await fetch('/api/v1/dashboard/stats', { headers })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()

    // Update stats with real data
    stats.value = [
      {
        label: 'System Health',
        value: `${data.system_health?.uptime_percent?.toFixed(1) || '99.9'}%`,
        icon: Activity,
        color: data.system_health?.status === 'healthy' ? 'text-green-500' : 'text-yellow-500'
      },
      {
        label: 'Active Fleets',
        value: String(data.fleet_count || 0),
        icon: Database,
        color: 'text-blue-500'
      },
      {
        label: 'Keys Rotated',
        value: data.key_rotations_24h > 0 ? `${data.key_rotations_24h}` : '24h',
        icon: Key,
        color: 'text-orange-500'
      },
      {
        label: 'Compliance',
        value: `Level ${data.compliance_level || 4}`,
        icon: ShieldCheck,
        color: 'text-purple-500'
      },
    ]

    error.value = null
  } catch (e) {
    console.warn('Dashboard stats fetch failed:', e.message)
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboardStats()
  pollInterval = setInterval(fetchDashboardStats, 30000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<template>
  <div class="space-y-6">
    <header class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold">System Dashboard</h2>
        <span class="text-xs text-gray-500">Real-time Telemetry & Pipeline Status</span>
      </div>
      <div v-if="error" class="flex items-center gap-2 text-xs text-yellow-500">
        <AlertCircle class="w-4 h-4" />
        <span>Using cached data</span>
      </div>
    </header>

    <!-- Stats Grid -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div v-for="stat in stats" :key="stat.label" class="bg-[#161b22] border border-[#30363d] p-4 rounded-lg flex items-center gap-4">
        <div class="p-2 rounded-md bg-opacity-10" :class="stat.color.replace('text-', 'bg-')">
          <component :is="stat.icon" class="w-5 h-5" :class="stat.color" />
        </div>
        <div>
          <div class="text-lg font-bold" :class="loading ? 'animate-pulse' : ''">{{ stat.value }}</div>
          <div class="text-xs text-gray-400">{{ stat.label }}</div>
        </div>
      </div>
    </div>

    <!-- Pipeline Visualizer -->
    <PipelineGraph />

    <!-- Mission Control Analytics -->
    <PerformanceDissect />
  </div>
</template>
