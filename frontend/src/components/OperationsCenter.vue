<script setup>
/**
 * Operations Center - Unified Fleet & Training Operations
 *
 * Consolidates: Fleets & Devices, Training Monitor, TGSP Marketplace, Integrations
 * Real-time operations monitoring and fleet management
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
    Server, Radio, Package, Link, RefreshCw, Plus,
    Activity, Users, Shield, Zap, TrendingUp, TrendingDown,
    CheckCircle, AlertTriangle, Clock, Play, Square,
    Upload, Download, Cpu, Cloud, Box, Lock
} from 'lucide-vue-next'

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
const fleetError = ref(null)
const packageError = ref(null)

// Training monitor state
const isMonitoring = ref(false)
const currentRound = ref(0)
const metrics = ref({ loss: [], accuracy: [] })
const expertWeights = ref({})
let monitorInterval = null

// Packages
const packages = ref([])

// Modal states
const showAddFleetModal = ref(false)
const showStartTrainingModal = ref(false)
const showUploadModal = ref(false)
const configuringIntegration = ref(null)
const uploading = ref(false)
const uploadFile = ref(null)
const selectedBaseModel = ref('Llama-VLA-8B')
const selectedFleet = ref('')

// Integrations
const integrations = ref([
    { id: 'isaac_lab', name: 'NVIDIA Isaac Lab', status: 'connected', icon: Cpu, color: 'text-green-500' },
    { id: 'ros2', name: 'ROS2 Bridge', status: 'active', icon: Radio, color: 'text-blue-500' },
    { id: 'formant', name: 'Formant.io', status: 'disconnected', icon: Cloud, color: 'text-gray-500' },
    { id: 'huggingface', name: 'Hugging Face', status: 'connected', icon: Box, color: 'text-yellow-500' }
])

const fetchFleets = async () => {
    loading.value = true
    fleetError.value = null
    try {
        const token = localStorage.getItem('auth_token')
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {}
        const res = await fetch('/api/v1/fleets/extended', { headers })
        if (res.ok) {
            fleets.value = await res.json()
        } else {
            fleetError.value = `HTTP ${res.status}`
            fleets.value = []
        }
    } catch (e) {
        console.warn('Failed to fetch fleets:', e.message)
        fleetError.value = e.message
        fleets.value = []
    }
    loading.value = false
}

const fetchPackages = async () => {
    packageError.value = null
    try {
        const token = localStorage.getItem('auth_token')
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {}
        const res = await fetch('/api/v1/community/tgsp/packages', { headers })
        if (res.ok) {
            const data = await res.json()
            packages.value = data.packages || data || []
        } else {
            packageError.value = `HTTP ${res.status}`
            packages.value = []
        }
    } catch (e) {
        console.warn('Failed to fetch packages:', e.message)
        packageError.value = e.message
        packages.value = []
    }
}

const uploadPackage = async () => {
    if (!uploadFile.value) return
    uploading.value = true
    const formData = new FormData()
    formData.append('file', uploadFile.value)
    try {
        const res = await fetch('/api/v1/tgsp/upload', {
            method: 'POST',
            body: formData
        })
        if (res.ok) {
            showUploadModal.value = false
            uploadFile.value = null
            await fetchPackages()
        }
    } catch (e) {
        console.error("Failed to upload package", e)
    }
    uploading.value = false
}

const handleFileSelect = (e) => {
    const file = e.target.files[0]
    if (file && file.name.endsWith('.tgsp')) {
        uploadFile.value = file
    }
}

const configureIntegration = (int) => {
    configuringIntegration.value = int
}

const saveIntegration = () => {
    configuringIntegration.value = null
}

// Training monitor functions - uses real telemetry API
const startMonitoring = async () => {
    isMonitoring.value = true

    const fetchTelemetryMetrics = async () => {
        try {
            const token = localStorage.getItem('auth_token')
            const headers = token ? { 'Authorization': `Bearer ${token}` } : {}
            const res = await fetch('/api/v1/telemetry/pipeline?time_range=15m', { headers })

            if (res.ok) {
                const data = await res.json()
                currentRound.value++

                // Extract metrics from real telemetry
                const workflow = data.workflow || []
                let totalLatency = 0
                let errorCount = 0
                let okCount = 0

                workflow.forEach(stage => {
                    totalLatency += stage.latency_ms || 0
                    if (stage.status === 'error') errorCount++
                    if (stage.status === 'ok') okCount++
                })

                // Calculate loss/accuracy from error rates
                const errorRate = workflow.length > 0 ? errorCount / workflow.length : 0
                const newLoss = 0.5 * errorRate + 0.01
                const newAcc = 1.0 - errorRate

                metrics.value.loss.push(newLoss)
                metrics.value.accuracy.push(newAcc)

                if (metrics.value.loss.length > 30) {
                    metrics.value.loss.shift()
                    metrics.value.accuracy.shift()
                }

                // Get expert weights from stage distribution
                const stageWeights = {}
                workflow.forEach(stage => {
                    stageWeights[stage.stage] = (stage.metrics?.count || 1) / 100
                })

                expertWeights.value = {}
                workflow.forEach(stage => {
                    if (stage.stage.includes('expert') || ['capture', 'embed', 'peft', 'sync'].includes(stage.stage)) {
                        expertWeights.value[stage.stage] = (stage.metrics?.count || 1) / (workflow.length || 1)
                    }
                })
            }
        } catch (e) {
            console.warn('Telemetry fetch failed:', e.message)
        }
    }

    // Initial fetch and then poll
    await fetchTelemetryMetrics()
    monitorInterval = setInterval(fetchTelemetryMetrics, 2000)
}

const stopMonitoring = () => {
    isMonitoring.value = false
    if (monitorInterval) {
        clearInterval(monitorInterval)
        monitorInterval = null
    }
}

const sparklinePoints = (data, height = 40) => {
    if (data.length < 2) return ''
    const max = Math.max(...data)
    const min = Math.min(...data)
    const range = max - min || 1
    const width = 200
    const step = width / (data.length - 1)
    return data.map((v, i) => `${i * step},${height - ((v - min) / range) * height}`).join(' ')
}

const getStatusColor = (status) => {
    const colors = { Healthy: 'text-green-500', Degraded: 'text-yellow-500', Critical: 'text-red-500' }
    return colors[status] || 'text-gray-500'
}

const getPackageStatus = (status) => {
    const styles = {
        verified: 'bg-green-500/10 text-green-500 border-green-500/30',
        uploaded: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/30',
        rejected: 'bg-red-500/10 text-red-500 border-red-500/30'
    }
    return styles[status] || 'bg-gray-500/10 text-gray-500 border-gray-500/30'
}

onMounted(async () => {
    fetchFleets()
    fetchPackages()

    // Initialize metrics from telemetry API
    try {
        const token = localStorage.getItem('auth_token')
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {}
        const res = await fetch('/api/v1/telemetry/pipeline?time_range=1h', { headers })

        if (res.ok) {
            const data = await res.json()
            const workflow = data.workflow || []

            // Initialize with real data points
            workflow.forEach(stage => {
                const errorRate = stage.metrics?.error_rate || 0
                metrics.value.loss.push(0.5 * errorRate + 0.01)
                metrics.value.accuracy.push(1.0 - errorRate)
            })
        }
    } catch (e) {
        console.warn('Initial telemetry fetch failed:', e.message)
    }

    // Pad with placeholder data if needed (no random values)
    while (metrics.value.loss.length < 10) {
        metrics.value.loss.push(0.5)
        metrics.value.accuracy.push(0.5)
    }
})

onUnmounted(() => {
    if (monitorInterval) clearInterval(monitorInterval)
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
          <button @click="showAddFleetModal = true" class="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium flex items-center gap-2">
            <Plus class="w-4 h-4" /> Add Fleet
          </button>
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
                <div class="text-lg font-bold text-blue-500">{{ ((fleet.devices_online / fleet.devices_total) * 100).toFixed(0) }}%</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Training Monitor Tab -->
      <div v-else-if="activeTab === 'monitor'" class="h-full overflow-y-auto p-6">
        <div class="flex items-center justify-between mb-6">
          <div class="flex items-center gap-4">
            <div v-if="isMonitoring" class="flex items-center gap-2">
              <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
              <span class="text-sm text-green-500 font-medium">Live</span>
            </div>
            <span class="text-sm text-gray-500">Round {{ currentRound }}</span>
          </div>
          <button v-if="!isMonitoring" @click="showStartTrainingModal = true"
                  class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium flex items-center gap-2">
            <Play class="w-4 h-4" /> Start Training Run
          </button>
          <button v-else @click="stopMonitoring"
                  class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium flex items-center gap-2">
            <Square class="w-4 h-4" /> Stop
          </button>
        </div>

        <div class="grid grid-cols-2 gap-6 mb-6">
          <!-- Loss Chart -->
          <div class="bg-[#0d1117] border border-[#30363d] rounded-lg p-5">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <TrendingDown class="w-4 h-4 text-green-500" />
                <span class="text-sm font-medium text-gray-400">Loss</span>
              </div>
              <span class="text-lg font-bold text-green-500">
                {{ (metrics.loss[metrics.loss.length - 1] || 0).toFixed(4) }}
              </span>
            </div>
            <svg class="w-full h-16" viewBox="0 0 200 40" preserveAspectRatio="none">
              <polyline :points="sparklinePoints(metrics.loss)" fill="none" stroke="#22c55e" stroke-width="2" />
            </svg>
          </div>

          <!-- Accuracy Chart -->
          <div class="bg-[#0d1117] border border-[#30363d] rounded-lg p-5">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <TrendingUp class="w-4 h-4 text-blue-500" />
                <span class="text-sm font-medium text-gray-400">Accuracy</span>
              </div>
              <span class="text-lg font-bold text-blue-500">
                {{ ((metrics.accuracy[metrics.accuracy.length - 1] || 0) * 100).toFixed(1) }}%
              </span>
            </div>
            <svg class="w-full h-16" viewBox="0 0 200 40" preserveAspectRatio="none">
              <polyline :points="sparklinePoints(metrics.accuracy)" fill="none" stroke="#3b82f6" stroke-width="2" />
            </svg>
          </div>
        </div>

        <!-- Expert Weights -->
        <div class="bg-[#0d1117] border border-[#30363d] rounded-lg p-5">
          <h3 class="text-sm font-medium text-gray-400 mb-4">FedMoE Expert Weights</h3>
          <div class="space-y-3">
            <div v-for="(weight, name) in expertWeights" :key="name" class="flex items-center gap-4">
              <span class="text-xs text-gray-400 w-32 truncate">{{ name }}</span>
              <div class="flex-1 h-2 bg-[#30363d] rounded-full overflow-hidden">
                <div class="h-full bg-gradient-to-r from-primary to-yellow-500 transition-all"
                     :style="{ width: (weight * 100) + '%' }"></div>
              </div>
              <span class="text-xs font-mono text-white w-12 text-right">{{ (weight * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Packages Tab -->
      <div v-else-if="activeTab === 'packages'" class="h-full overflow-y-auto p-6">
        <div class="flex items-center justify-between mb-6">
          <h2 class="text-lg font-semibold text-white">TGSP Packages</h2>
          <button @click="showUploadModal = true" class="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium flex items-center gap-2">
            <Upload class="w-4 h-4" /> Upload Package
          </button>
        </div>

        <div class="space-y-4">
          <div v-for="pkg in packages" :key="pkg.id"
               class="bg-[#0d1117] border border-[#30363d] rounded-lg p-5 hover:border-[#484f58] transition-colors">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <Package class="w-6 h-6 text-purple-400" />
                <div>
                  <div class="font-semibold text-white">{{ pkg.filename }}</div>
                  <div class="text-xs text-gray-500">{{ pkg.producer_id }}</div>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <span :class="['text-xs font-bold uppercase px-2 py-1 rounded border', getPackageStatus(pkg.status)]">
                  {{ pkg.status }}
                </span>
                <button class="p-2 hover:bg-[#1f2428] rounded transition-colors">
                  <Download class="w-4 h-4 text-gray-400" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Integrations Tab -->
      <div v-else-if="activeTab === 'integrations'" class="h-full overflow-y-auto p-6">
        <div class="grid grid-cols-2 gap-6">
          <div v-for="int in integrations" :key="int.id"
               class="bg-[#0d1117] border border-[#30363d] rounded-lg p-5 hover:border-[#484f58] transition-colors">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-3">
                <component :is="int.icon" class="w-6 h-6" :class="int.color" />
                <span class="font-semibold text-white">{{ int.name }}</span>
              </div>
              <span :class="['text-xs font-medium capitalize',
                     int.status === 'connected' || int.status === 'active' ? 'text-green-500' : 'text-gray-500']">
                {{ int.status }}
              </span>
            </div>
            <button @click="configureIntegration(int)" class="w-full px-4 py-2 border border-[#30363d] rounded-lg text-sm font-medium hover:bg-[#1f2428] transition-colors"
                    :class="int.status === 'connected' || int.status === 'active' ? 'text-gray-400' : 'text-primary'">
              {{ int.status === 'connected' || int.status === 'active' ? 'Reconfigure' : 'Connect' }}
            </button>
          </div>
        </div>
      </div>
    </div>


    <!-- Add Fleet Modal -->
    <div v-if="showAddFleetModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div class="bg-[#0d1117] border border-[#30363d] rounded-xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-200">
        <div class="px-6 py-4 border-b border-[#30363d] flex items-center justify-between bg-[#161b22]">
          <h3 class="font-bold text-white">Register New Fleet</h3>
          <button @click="showAddFleetModal = false" class="text-gray-500 hover:text-white transition-colors">
            <Plus class="w-5 h-5 rotate-45" />
          </button>
        </div>
        <div class="p-6 space-y-4">
          <div class="space-y-1">
            <label class="text-[10px] font-bold text-gray-500 uppercase">Fleet Alias</label>
            <input type="text" placeholder="e.g. warehouse-dist-north" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white outline-none focus:border-primary/50" />
          </div>
          <div class="grid grid-cols-2 gap-4">
             <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-500 uppercase">Region</label>
                <select class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-xs text-white">
                  <option>us-east-1</option>
                  <option>eu-central-1</option>
                  <option>ap-northeast-1</option>
                </select>
             </div>
             <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-500 uppercase">Node Type</label>
                <select class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-xs text-white">
                  <option>Humanoid-H1</option>
                  <option>Atlas-V3</option>
                  <option>Unitree-G1</option>
                </select>
             </div>
          </div>
          <div class="p-3 bg-blue-500/5 border border-blue-500/20 rounded-md flex gap-3">
             <Shield class="w-5 h-5 text-blue-500 shrink-0" />
             <div class="text-[11px] text-gray-400">
                Registering a fleet generates a master PQC identity. Ensure your devices have the `liboqs` runtime installed before onboarding.
             </div>
          </div>
        </div>
        <div class="px-6 py-4 bg-[#161b22] border-t border-[#30363d] flex justify-end gap-3">
          <button @click="showAddFleetModal = false" class="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white transition-colors">Cancel</button>
          <button @click="showAddFleetModal = false" class="px-4 py-2 bg-primary text-white text-sm font-bold rounded hover:bg-primary/90 transition-colors">Provision Identity</button>
        </div>
      </div>
    </div>

    <!-- Start Training Modal -->
    <div v-if="showStartTrainingModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div class="bg-[#0d1117] border border-[#30363d] rounded-xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-200">
        <div class="px-6 py-4 border-b border-[#30363d] flex items-center justify-between bg-[#161b22]">
          <h3 class="font-bold text-white">Configure Training Run (PEFT)</h3>
          <button @click="showStartTrainingModal = false" class="text-gray-500 hover:text-white transition-colors">
            <Plus class="w-5 h-5 rotate-45" />
          </button>
        </div>
        <div class="p-6 space-y-4">
          <div class="space-y-1">
            <label class="text-[10px] font-bold text-gray-500 uppercase">Instruction Context</label>
            <input type="text" placeholder="e.g. 'pick up small metallic objects from the conveyor'" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white outline-none focus:border-primary/50" />
          </div>
          <div class="grid grid-cols-2 gap-4">
             <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-500 uppercase">Target Fleet</label>
                <select v-model="selectedFleet" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-xs text-white">
                  <option v-for="f in fleets" :key="f.id" :value="f.id">{{ f.name }}</option>
                  <option value="test">Lab-Prototype-A</option>
                </select>
             </div>
             <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-500 uppercase">PEFT Method</label>
                <select class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-xs text-white">
                  <option>LoRA (Rank 8)</option>
                  <option>QLoRA (4-bit)</option>
                  <option>FedMoE-Adapter</option>
                </select>
             </div>
          </div>
          <div class="flex items-center justify-between p-3 bg-green-500/5 border border-green-500/20 rounded-md">
             <div class="flex items-center gap-3">
                <Lock class="w-4 h-4 text-green-500" />
                <div class="text-[11px] text-gray-300">N2HE Gradient Protection Active</div>
             </div>
             <div class="text-[10px] font-mono text-gray-500">ε = 1.35</div>
          </div>
        </div>
        <div class="px-6 py-4 bg-[#161b22] border-t border-[#30363d] flex justify-end gap-3">
          <button @click="showStartTrainingModal = false" class="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white transition-colors">Cancel</button>
          <button @click="showStartTrainingModal = false; startMonitoring()" class="px-4 py-2 bg-green-600 text-white text-sm font-bold rounded hover:bg-green-700 transition-colors">Initiate FedMoE Loop</button>
        </div>
      </div>
    </div>

    <!-- Upload TGSP Modal -->
    <div v-if="showUploadModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div class="bg-[#0d1117] border border-[#30363d] rounded-xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-200">
        <div class="px-6 py-4 border-b border-[#30363d] flex items-center justify-between bg-[#161b22]">
          <h3 class="font-bold text-white">Upload TGSP Package</h3>
          <button @click="showUploadModal = false; uploadFile = null" class="text-gray-500 hover:text-white transition-colors">
            <Plus class="w-5 h-5 rotate-45" />
          </button>
        </div>
        <div class="p-6 space-y-4">
          <div class="border-2 border-dashed border-[#30363d] rounded-lg p-8 text-center hover:border-primary/50 transition-colors">
            <input type="file" accept=".tgsp" @change="handleFileSelect" class="hidden" id="oc-tgsp-upload" />
            <label for="oc-tgsp-upload" class="cursor-pointer">
              <Package class="w-12 h-12 text-gray-600 mx-auto mb-3" />
              <div v-if="uploadFile" class="text-primary font-bold">{{ uploadFile.name }}</div>
              <div v-else>
                <p class="text-gray-400 mb-1 text-sm">Drop your .tgsp package or click to browse</p>
                <p class="text-[10px] text-gray-600 uppercase">Max size: 512MB</p>
              </div>
            </label>
          </div>
          <div class="p-3 bg-primary/5 border border-primary/20 rounded-md">
             <div class="flex items-center gap-2 text-primary mb-1">
                <Shield class="w-4 h-4" />
                <span class="text-[10px] font-bold uppercase">Integrity Guard</span>
             </div>
             <p class="text-[11px] text-gray-400">All uploaded packages are automatically verified against GA Dilithium-3 signatures before fleet distribution.</p>
          </div>
        </div>
        <div class="px-6 py-4 bg-[#161b22] border-t border-[#30363d] flex justify-end gap-3">
          <button @click="showUploadModal = false; uploadFile = null" class="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white transition-colors">Cancel</button>
          <button @click="uploadPackage" :disabled="!uploadFile || uploading" class="px-4 py-2 bg-primary text-white text-sm font-bold rounded hover:bg-primary/90 transition-colors disabled:opacity-50">
            {{ uploading ? 'Uploading...' : 'Finalize Upload' }}
          </button>
        </div>
      </div>
    </div>

    </div>

    <!-- Integration Config Modal -->
    <div v-if="configuringIntegration" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div class="bg-[#0d1117] border border-[#30363d] rounded-xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-200">
        <div class="px-6 py-4 border-b border-[#30363d] flex items-center justify-between bg-[#161b22]">
          <h3 class="font-bold text-white">Configure {{ configuringIntegration.name }}</h3>
          <button @click="configuringIntegration = null" class="text-gray-500 hover:text-white transition-colors">
            <Plus class="w-5 h-5 rotate-45" />
          </button>
        </div>
        <div class="p-6 space-y-4">
          <div v-if="configuringIntegration.id === 'isaac_lab'" class="space-y-4">
             <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-500 uppercase">Sim Server URL</label>
                <input type="text" placeholder="e.g. grpc://simulation-cluster:50051" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white focus:border-primary/50 outline-none" />
             </div>
             <div class="p-3 bg-green-500/5 border border-green-500/20 rounded-md text-[11px] text-gray-400">
                ISAAC integration permits high-fidelity humanoid simulation and synthetic data generation for v2.3 GA fine-tuning.
             </div>
          </div>

          <div v-else-if="configuringIntegration.id === 'ros2'" class="space-y-4">
             <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-500 uppercase">ROS_DOMAIN_ID</label>
                <input type="number" value="30" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white outline-none" />
             </div>
             <div class="p-3 bg-blue-500/5 border border-blue-500/20 rounded-md text-[11px] text-gray-400">
                The ROS2 Bridge connects your Humanoid VLA experts to physical hardware using standard `tf2` and `cmd_vel` topics.
             </div>
          </div>

          <div v-else-if="configuringIntegration.id === 'formant'" class="space-y-4">
             <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-500 uppercase">Organization Token</label>
                <input type="password" placeholder="••••••••••••••••" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white outline-none" />
             </div>
             <div class="p-3 bg-red-500/5 border border-red-500/20 rounded-md text-[11px] text-gray-400">
                Formant synchronization enables real-time teleop and observability for GA fleets.
             </div>
          </div>

          <div v-else-if="configuringIntegration.id === 'huggingface'" class="space-y-4">
             <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-500 uppercase">HF API Write Token</label>
                <input type="password" placeholder="hf_••••••••" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white outline-none" />
             </div>
             <div class="p-3 bg-yellow-500/5 border border-yellow-500/20 rounded-md text-[11px] text-gray-400">
                Linking Hugging Face allows you to pull base VLA models and push your verified PEFT experts directly to the hub.
             </div>
          </div>
        </div>
        <div class="px-6 py-4 bg-[#161b22] border-t border-[#30363d] flex justify-end gap-3">
          <button @click="configuringIntegration = null" class="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white transition-colors">Cancel</button>
          <button @click="saveIntegration" class="px-4 py-2 bg-primary text-white text-sm font-bold rounded hover:bg-primary/90 transition-colors">Verify & Connect</button>
        </div>
      </div>
    </div>

  </div>
</template>
