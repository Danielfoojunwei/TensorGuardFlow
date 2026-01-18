<script setup>
/**
 * Pipeline Graph - Real-time Pipeline Status Visualization
 *
 * Displays the 7-stage TensorGuard pipeline with real telemetry data:
 * - capture → embed → gate → peft → shield → sync → pull
 *
 * Fetches from /api/v1/telemetry/pipeline and displays:
 * - Stage status (ok, degraded, error)
 * - Latency values
 * - Animated data flow visualization
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { CheckCircle, AlertTriangle, XCircle, Clock } from 'lucide-vue-next'

// 7 Stages of the TensorGuard Pipeline (matching backend stages)
const baseStages = [
  { id: 'capture', label: 'Capture', x: 50, color: '#f97316' },
  { id: 'embed', label: 'Embed', x: 200, color: '#3b82f6' },
  { id: 'gate', label: 'Gate', x: 350, color: '#a855f7' },
  { id: 'peft', label: 'PEFT', x: 500, color: '#10b981' },
  { id: 'shield', label: 'Shield', x: 650, color: '#ef4444' },
  { id: 'sync', label: 'Sync', x: 800, color: '#eab308' },
  { id: 'pull', label: 'Pull', x: 950, color: '#06b6d4' }
]

const stages = ref(baseStages.map(s => ({ ...s, status: 'unknown', latency_ms: 0 })))
const loading = ref(true)
const error = ref(null)
const safeMode = ref(false)
let pollInterval = null

const fetchPipelineData = async () => {
  try {
    const token = localStorage.getItem('auth_token')
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {}
    const res = await fetch('/api/v1/telemetry/pipeline?time_range=15m', { headers })

    if (res.ok) {
      const data = await res.json()
      safeMode.value = data.safe_mode || false

      // Update stages with real data
      const workflow = data.workflow || []
      stages.value = baseStages.map(base => {
        const stageData = workflow.find(w => w.stage === base.id)
        return {
          ...base,
          status: stageData?.status || 'unknown',
          latency_ms: stageData?.latency_ms || 0,
          metrics: stageData?.metrics || {}
        }
      })

      error.value = null
    } else {
      error.value = `HTTP ${res.status}`
    }
  } catch (e) {
    console.warn('Pipeline data fetch failed:', e.message)
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const paths = ref([])

onMounted(() => {
  // Generate distinct 'threads' for the braid visualization
  for (let i = 0; i < 5; i++) {
    const d = generatePath(i * 10)
    paths.value.push({ d, color: baseStages[i % baseStages.length].color })
  }

  // Fetch real data
  fetchPipelineData()
  pollInterval = setInterval(fetchPipelineData, 10000) // Poll every 10 seconds
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})

function generatePath(offset) {
  let d = `M 50 ${150 + offset}`
  baseStages.forEach((s, i) => {
    if (i === 0) return
    const prev = baseStages[i-1]
    const cp1x = prev.x + (s.x - prev.x) / 2
    const cp1y = 150 + offset
    const cp2x = prev.x + (s.x - prev.x) / 2
    const cp2y = 150 + offset + (i % 2 === 0 ? 20 : -20)
    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${s.x} ${150 + offset}`
  })
  return d
}

const getStatusColor = (status) => {
  const colors = {
    ok: '#22c55e',
    degraded: '#eab308',
    error: '#ef4444',
    unknown: '#6b7280'
  }
  return colors[status] || colors.unknown
}

const getStatusIcon = (status) => {
  if (status === 'ok') return CheckCircle
  if (status === 'error') return XCircle
  if (status === 'degraded') return AlertTriangle
  return Clock
}
</script>

<template>
  <div class="w-full overflow-x-auto bg-[#0d1117] rounded-lg border border-[#30363d] p-6 relative">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-bold text-gray-400 uppercase tracking-wider">TensorGuard Pipeline Status</h3>
      <div class="flex items-center gap-3">
        <div v-if="safeMode" class="flex items-center gap-1 px-2 py-1 bg-yellow-500/10 border border-yellow-500/30 rounded text-yellow-500 text-xs">
          <AlertTriangle class="w-3 h-3" />
          <span>Safe Mode</span>
        </div>
        <div v-if="error" class="text-xs text-gray-500">Using cached data</div>
      </div>
    </div>

    <svg width="1050" height="300" class="w-full h-auto">
      <!-- Connecting Lines (The Braid) -->
      <path v-for="(p, i) in paths" :key="i"
            :d="p.d"
            fill="none"
            :stroke="p.color"
            stroke-width="2"
            stroke-opacity="0.3"
      />

      <!-- Active Particles (Data Flow) -->
      <circle v-for="(p, i) in paths" :key="`p-${i}`" r="3" fill="white">
        <animateMotion :path="p.d" dur="3s" repeatCount="indefinite" :begin="`${i * 0.5}s`" />
      </circle>

      <!-- Stage Nodes with Real Status -->
      <g v-for="stage in stages" :key="stage.id" :transform="`translate(${stage.x}, 150)`">
        <!-- Outer ring - status color -->
        <circle r="18" :fill="getStatusColor(stage.status)" fill-opacity="0.1" :stroke="getStatusColor(stage.status)" stroke-width="2" />
        <!-- Inner circle -->
        <circle r="8" :fill="stage.color" class="drop-shadow-lg" />
        <!-- Pulse animation for active stages -->
        <circle v-if="stage.status === 'ok'" r="18" :stroke="stage.color" stroke-opacity="0.3" fill="none" class="animate-pulse" />

        <!-- Status indicator -->
        <g transform="translate(12, -12)">
          <circle r="6" :fill="getStatusColor(stage.status)" />
        </g>

        <!-- Label -->
        <text y="38" text-anchor="middle" fill="#8b949e" class="text-xs font-mono">{{ stage.label }}</text>
        <!-- Latency -->
        <text y="52" text-anchor="middle" :fill="stage.latency_ms > 100 ? '#eab308' : '#6b7280'" class="text-xs font-mono">
          {{ stage.latency_ms > 0 ? `${stage.latency_ms.toFixed(0)}ms` : '—' }}
        </text>
      </g>
    </svg>

    <!-- Legend -->
    <div class="flex items-center justify-center gap-6 mt-4 text-xs text-gray-500">
      <div class="flex items-center gap-1">
        <div class="w-3 h-3 rounded-full bg-green-500"></div>
        <span>OK</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-3 h-3 rounded-full bg-yellow-500"></div>
        <span>Degraded</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-3 h-3 rounded-full bg-red-500"></div>
        <span>Error</span>
      </div>
      <div class="flex items-center gap-1">
        <div class="w-3 h-3 rounded-full bg-gray-500"></div>
        <span>Unknown</span>
      </div>
    </div>
  </div>
</template>
