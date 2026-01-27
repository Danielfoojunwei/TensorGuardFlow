<script setup>
import { ref, onMounted, computed } from 'vue'
import {
    Network, RefreshCw, CheckCircle, XCircle, AlertTriangle,
    Database, Server, FileOutput, Shield, Eye, Activity,
    Download, Settings, Play, ChevronRight, Layers,
    Cloud, Cpu, Box, Lock, ArrowRight
} from 'lucide-vue-next'

const topology = ref(null)
const loading = ref(true)
const error = ref(null)
const selectedNode = ref(null)
const showExportModal = ref(false)
const exportTarget = ref('kubernetes')
const exportRouteKey = ref('')
const exporting = ref(false)
const exportResult = ref(null)

const categoryIcons = {
    C: Database,
    D: Cpu,
    E: Layers,
    F: Server,
    G: Shield
}

const categoryColors = {
    C: { bg: 'bg-blue-500/10', text: 'text-blue-500', border: 'border-blue-500/30' },
    D: { bg: 'bg-green-500/10', text: 'text-green-500', border: 'border-green-500/30' },
    E: { bg: 'bg-purple-500/10', text: 'text-purple-500', border: 'border-purple-500/30' },
    F: { bg: 'bg-orange-500/10', text: 'text-orange-500', border: 'border-orange-500/30' },
    G: { bg: 'bg-red-500/10', text: 'text-red-500', border: 'border-red-500/30' }
}

const categoryNames = {
    C: 'Data Sources',
    D: 'Training',
    E: 'Registry',
    F: 'Serving',
    G: 'Trust & Privacy'
}

const statusColors = {
    OK: 'text-green-500',
    WARN: 'text-yellow-500',
    FAIL: 'text-red-500',
    UNKNOWN: 'text-gray-500',
    DISABLED: 'text-gray-600'
}

const exportTargets = [
    { id: 'kubernetes', name: 'Kubernetes', icon: Server },
    { id: 'sagemaker', name: 'AWS SageMaker', icon: Cloud },
    { id: 'vertex', name: 'Google Vertex AI', icon: Cloud },
    { id: 'azureml', name: 'Azure ML', icon: Cloud },
    { id: 'databricks', name: 'Databricks', icon: Database },
    { id: 'vllm', name: 'vLLM', icon: Cpu },
    { id: 'tgi', name: 'TGI', icon: Cpu },
    { id: 'triton', name: 'Triton', icon: Cpu }
]

const fetchTopology = async () => {
    loading.value = true
    error.value = null
    try {
        const res = await fetch('/api/v1/integrations/topology')
        if (res.ok) {
            const data = await res.json()
            topology.value = data.data
        } else {
            error.value = 'Failed to fetch topology'
        }
    } catch (e) {
        console.error("Failed to fetch topology", e)
        error.value = e.message
    }
    loading.value = false
}

const triggerHealthCheck = async () => {
    loading.value = true
    try {
        await fetch('/api/v1/integrations/healthcheck', { method: 'POST' })
        await fetchTopology()
    } catch (e) {
        console.error("Health check failed", e)
    }
    loading.value = false
}

const nodesByCategory = computed(() => {
    if (!topology.value?.nodes) return {}
    const grouped = {}
    for (const node of topology.value.nodes) {
        const cat = node.category
        if (!grouped[cat]) grouped[cat] = []
        grouped[cat].push(node)
    }
    return grouped
})

const overallHealth = computed(() => {
    return topology.value?.summary?.overall_health || 'UNKNOWN'
})

const overallHealthColor = computed(() => {
    const health = overallHealth.value
    if (health === 'HEALTHY') return 'text-green-500'
    if (health === 'DEGRADED') return 'text-yellow-500'
    return 'text-red-500'
})

const selectNode = (node) => {
    selectedNode.value = node
}

const openExportModal = () => {
    showExportModal.value = true
    exportResult.value = null
}

const runExport = async () => {
    if (!exportRouteKey.value) {
        alert('Please enter a route key')
        return
    }
    exporting.value = true
    try {
        const res = await fetch('/api/v1/integrations/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                route_key: exportRouteKey.value,
                target: exportTarget.value,
                config_overrides: {}
            })
        })
        if (res.ok) {
            exportResult.value = await res.json()
        } else {
            const err = await res.json()
            alert(`Export failed: ${err.detail || err.message}`)
        }
    } catch (e) {
        console.error("Export failed", e)
        alert("Export failed. Check console for details.")
    }
    exporting.value = false
}

onMounted(fetchTopology)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-[#333] pb-6">
       <div>
         <h2 class="text-2xl font-bold flex items-center gap-3">
             <Network class="w-7 h-7 text-purple-500" />
             Integration Console
         </h2>
         <span class="text-xs text-gray-500">Full-stack integration topology view (C&rarr;D&rarr;E&rarr;F + G)</span>
       </div>
       <div class="flex gap-2">
           <button @click="openExportModal" class="btn btn-secondary">
               <FileOutput class="w-4 h-4 mr-2" />
               Export
           </button>
           <button @click="triggerHealthCheck" :disabled="loading" class="btn btn-secondary">
               <RefreshCw class="w-4 h-4" :class="loading ? 'animate-spin' : ''" />
           </button>
       </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-12">
        <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
        <XCircle class="w-8 h-8 text-red-500 mx-auto mb-2" />
        <p class="text-red-500">{{ error }}</p>
        <button @click="fetchTopology" class="mt-4 btn btn-secondary">Retry</button>
    </div>

    <!-- Topology View -->
    <div v-else-if="topology" class="space-y-6">
        <!-- Health Summary -->
        <div class="bg-[#111] border border-[#333] rounded-lg p-6">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-4">
                    <div :class="['w-12 h-12 rounded-full flex items-center justify-center',
                                  overallHealth === 'HEALTHY' ? 'bg-green-500/20' :
                                  overallHealth === 'DEGRADED' ? 'bg-yellow-500/20' : 'bg-red-500/20']">
                        <Activity class="w-6 h-6" :class="overallHealthColor" />
                    </div>
                    <div>
                        <h3 class="text-lg font-bold" :class="overallHealthColor">{{ overallHealth }}</h3>
                        <p class="text-xs text-gray-500">Integration Health Status</p>
                    </div>
                </div>
                <div class="flex gap-8 text-center">
                    <div>
                        <div class="text-2xl font-bold text-white">{{ topology.summary?.total_nodes || 0 }}</div>
                        <div class="text-[10px] text-gray-500 uppercase">Nodes</div>
                    </div>
                    <div>
                        <div class="text-2xl font-bold text-green-500">{{ topology.summary?.nodes_by_status?.OK || 0 }}</div>
                        <div class="text-[10px] text-gray-500 uppercase">Healthy</div>
                    </div>
                    <div>
                        <div class="text-2xl font-bold text-yellow-500">{{ topology.summary?.nodes_by_status?.WARN || 0 }}</div>
                        <div class="text-[10px] text-gray-500 uppercase">Warning</div>
                    </div>
                    <div>
                        <div class="text-2xl font-bold text-red-500">{{ topology.summary?.nodes_by_status?.FAIL || 0 }}</div>
                        <div class="text-[10px] text-gray-500 uppercase">Failed</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Topology Flow Diagram -->
        <div class="bg-[#0d1117] border border-[#30363d] rounded-xl p-6">
            <h3 class="text-xs font-bold text-gray-500 uppercase mb-6 flex items-center gap-2">
                <Layers class="w-4 h-4" />
                Integration Topology Flow
            </h3>

            <div class="flex items-start justify-between gap-4">
                <!-- Category C: Data -->
                <div class="flex-1">
                    <div :class="['rounded-lg p-4 border', categoryColors.C.bg, categoryColors.C.border]">
                        <div class="flex items-center gap-2 mb-3">
                            <component :is="categoryIcons.C" class="w-5 h-5" :class="categoryColors.C.text" />
                            <span class="text-xs font-bold uppercase" :class="categoryColors.C.text">{{ categoryNames.C }}</span>
                        </div>
                        <div class="space-y-2">
                            <div v-for="node in (nodesByCategory.C || [])" :key="node.id"
                                 @click="selectNode(node)"
                                 class="bg-[#161b22] rounded p-2 cursor-pointer hover:bg-[#21262d] transition-colors">
                                <div class="flex items-center justify-between">
                                    <span class="text-xs text-white">{{ node.provider_display }}</span>
                                    <component :is="node.status === 'OK' ? CheckCircle : node.status === 'WARN' ? AlertTriangle : XCircle"
                                               class="w-3 h-3" :class="statusColors[node.status]" />
                                </div>
                            </div>
                            <div v-if="!nodesByCategory.C?.length" class="text-xs text-gray-600 italic">No data sources</div>
                        </div>
                    </div>
                </div>

                <ArrowRight class="w-6 h-6 text-gray-600 mt-12 flex-shrink-0" />

                <!-- Category D: Training -->
                <div class="flex-1">
                    <div :class="['rounded-lg p-4 border', categoryColors.D.bg, categoryColors.D.border]">
                        <div class="flex items-center gap-2 mb-3">
                            <component :is="categoryIcons.D" class="w-5 h-5" :class="categoryColors.D.text" />
                            <span class="text-xs font-bold uppercase" :class="categoryColors.D.text">{{ categoryNames.D }}</span>
                        </div>
                        <div class="space-y-2">
                            <div v-for="node in (nodesByCategory.D || [])" :key="node.id"
                                 @click="selectNode(node)"
                                 class="bg-[#161b22] rounded p-2 cursor-pointer hover:bg-[#21262d] transition-colors">
                                <div class="flex items-center justify-between">
                                    <span class="text-xs text-white">{{ node.provider_display }}</span>
                                    <component :is="node.status === 'OK' ? CheckCircle : node.status === 'WARN' ? AlertTriangle : XCircle"
                                               class="w-3 h-3" :class="statusColors[node.status]" />
                                </div>
                            </div>
                            <div v-if="!nodesByCategory.D?.length" class="text-xs text-gray-600 italic">No training</div>
                        </div>
                    </div>
                </div>

                <ArrowRight class="w-6 h-6 text-gray-600 mt-12 flex-shrink-0" />

                <!-- Category E: Registry -->
                <div class="flex-1">
                    <div :class="['rounded-lg p-4 border', categoryColors.E.bg, categoryColors.E.border]">
                        <div class="flex items-center gap-2 mb-3">
                            <component :is="categoryIcons.E" class="w-5 h-5" :class="categoryColors.E.text" />
                            <span class="text-xs font-bold uppercase" :class="categoryColors.E.text">{{ categoryNames.E }}</span>
                        </div>
                        <div class="space-y-2">
                            <div v-for="node in (nodesByCategory.E || [])" :key="node.id"
                                 @click="selectNode(node)"
                                 class="bg-[#161b22] rounded p-2 cursor-pointer hover:bg-[#21262d] transition-colors">
                                <div class="flex items-center justify-between">
                                    <span class="text-xs text-white">{{ node.provider_display }}</span>
                                    <component :is="node.status === 'OK' ? CheckCircle : node.status === 'WARN' ? AlertTriangle : XCircle"
                                               class="w-3 h-3" :class="statusColors[node.status]" />
                                </div>
                            </div>
                            <div v-if="!nodesByCategory.E?.length" class="text-xs text-gray-600 italic">No registry</div>
                        </div>
                    </div>
                </div>

                <ArrowRight class="w-6 h-6 text-gray-600 mt-12 flex-shrink-0" />

                <!-- Category F: Serving -->
                <div class="flex-1">
                    <div :class="['rounded-lg p-4 border', categoryColors.F.bg, categoryColors.F.border]">
                        <div class="flex items-center gap-2 mb-3">
                            <component :is="categoryIcons.F" class="w-5 h-5" :class="categoryColors.F.text" />
                            <span class="text-xs font-bold uppercase" :class="categoryColors.F.text">{{ categoryNames.F }}</span>
                        </div>
                        <div class="space-y-2">
                            <div v-for="node in (nodesByCategory.F || [])" :key="node.id"
                                 @click="selectNode(node)"
                                 class="bg-[#161b22] rounded p-2 cursor-pointer hover:bg-[#21262d] transition-colors">
                                <div class="flex items-center justify-between">
                                    <span class="text-xs text-white">{{ node.provider_display }}</span>
                                    <component :is="node.status === 'OK' ? CheckCircle : node.status === 'WARN' ? AlertTriangle : XCircle"
                                               class="w-3 h-3" :class="statusColors[node.status]" />
                                </div>
                            </div>
                            <div v-if="!nodesByCategory.F?.length" class="text-xs text-gray-600 italic">No serving</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Category G: Trust (Overlay) -->
            <div class="mt-6 pt-6 border-t border-[#30363d]">
                <div :class="['rounded-lg p-4 border', categoryColors.G.bg, categoryColors.G.border]">
                    <div class="flex items-center gap-2 mb-3">
                        <component :is="categoryIcons.G" class="w-5 h-5" :class="categoryColors.G.text" />
                        <span class="text-xs font-bold uppercase" :class="categoryColors.G.text">{{ categoryNames.G }} (Overlay)</span>
                    </div>
                    <div class="flex gap-4">
                        <div v-for="node in (nodesByCategory.G || [])" :key="node.id"
                             @click="selectNode(node)"
                             class="bg-[#161b22] rounded p-2 cursor-pointer hover:bg-[#21262d] transition-colors flex-1">
                            <div class="flex items-center justify-between">
                                <span class="text-xs text-white">{{ node.provider_display }}</span>
                                <component :is="node.status === 'OK' ? CheckCircle : node.status === 'WARN' ? AlertTriangle : XCircle"
                                           class="w-3 h-3" :class="statusColors[node.status]" />
                            </div>
                        </div>
                        <div v-if="!nodesByCategory.G?.length" class="text-xs text-gray-600 italic flex-1">No trust/privacy integrations</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Node Details Panel -->
        <div v-if="selectedNode" class="bg-[#111] border border-[#333] rounded-lg p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-bold text-white flex items-center gap-2">
                    <Eye class="w-5 h-5 text-purple-500" />
                    {{ selectedNode.provider_display }}
                </h3>
                <button @click="selectedNode = null" class="text-gray-500 hover:text-white">&times;</button>
            </div>
            <div class="grid grid-cols-2 gap-4 text-sm">
                <div>
                    <span class="text-gray-500">Provider:</span>
                    <span class="text-white ml-2 font-mono">{{ selectedNode.provider }}</span>
                </div>
                <div>
                    <span class="text-gray-500">Category:</span>
                    <span class="text-white ml-2">{{ categoryNames[selectedNode.category] }}</span>
                </div>
                <div>
                    <span class="text-gray-500">Status:</span>
                    <span class="ml-2" :class="statusColors[selectedNode.status]">{{ selectedNode.status }}</span>
                </div>
                <div>
                    <span class="text-gray-500">Latency:</span>
                    <span class="text-white ml-2 font-mono">{{ selectedNode.health_check_latency_ms || 'N/A' }}ms</span>
                </div>
                <div class="col-span-2" v-if="selectedNode.status_message">
                    <span class="text-gray-500">Message:</span>
                    <span class="text-gray-300 ml-2">{{ selectedNode.status_message }}</span>
                </div>
                <div class="col-span-2" v-if="selectedNode.capabilities?.length">
                    <span class="text-gray-500">Capabilities:</span>
                    <div class="mt-2 flex flex-wrap gap-2">
                        <span v-for="cap in selectedNode.capabilities" :key="cap"
                              class="px-2 py-1 bg-purple-500/10 text-purple-500 rounded text-xs">
                            {{ cap }}
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Edges Info -->
        <div v-if="topology.edges?.length" class="bg-[#111] border border-[#333] rounded-lg p-6">
            <h3 class="text-xs font-bold text-gray-500 uppercase mb-4 flex items-center gap-2">
                <ChevronRight class="w-4 h-4" />
                Data Flow Connections ({{ topology.edges.length }})
            </h3>
            <div class="space-y-2 max-h-48 overflow-y-auto">
                <div v-for="(edge, idx) in topology.edges" :key="idx"
                     class="flex items-center gap-2 text-xs p-2 bg-[#161b22] rounded">
                    <span class="font-mono text-white">{{ edge.from_node }}</span>
                    <ArrowRight class="w-3 h-3 text-gray-500" />
                    <span class="font-mono text-white">{{ edge.to_node }}</span>
                    <span class="text-gray-500">({{ edge.protocol }})</span>
                    <span v-if="edge.data_types?.length" class="text-gray-600">
                        [{{ edge.data_types.join(', ') }}]
                    </span>
                </div>
            </div>
        </div>
    </div>

    <!-- Export Modal -->
    <div v-if="showExportModal" class="fixed inset-0 bg-black/90 flex items-center justify-center z-50 backdrop-blur-sm p-4">
        <div class="bg-[#0f0f0f] border border-primary/30 w-full max-w-lg rounded-xl shadow-2xl overflow-hidden">
            <div class="p-6 border-b border-[#222] flex items-center gap-4">
                <div class="w-12 h-12 rounded-xl bg-purple-500/10 flex items-center justify-center">
                    <FileOutput class="w-6 h-6 text-purple-500" />
                </div>
                <div>
                    <h3 class="text-xl font-bold text-white">Export Artifacts</h3>
                    <p class="text-[10px] text-gray-500 uppercase mt-1">Generate platform-specific deployment files</p>
                </div>
            </div>
            <div class="p-6 space-y-4">
                <div>
                    <label class="text-[10px] text-gray-500 font-bold uppercase mb-2 block">Route Key</label>
                    <input v-model="exportRouteKey"
                           type="text"
                           placeholder="customer-support-v1"
                           class="w-full bg-[#111] border border-[#333] rounded px-4 py-3 text-sm focus:border-primary outline-none transition-colors" />
                </div>
                <div>
                    <label class="text-[10px] text-gray-500 font-bold uppercase mb-2 block">Target Platform</label>
                    <div class="grid grid-cols-4 gap-2">
                        <button v-for="target in exportTargets" :key="target.id"
                                @click="exportTarget = target.id"
                                :class="['p-3 rounded border text-center transition-colors',
                                        exportTarget === target.id ? 'border-primary bg-primary/10' : 'border-[#333] hover:border-[#444]']">
                            <component :is="target.icon" class="w-5 h-5 mx-auto mb-1" :class="exportTarget === target.id ? 'text-primary' : 'text-gray-500'" />
                            <span class="text-[10px]" :class="exportTarget === target.id ? 'text-white' : 'text-gray-500'">{{ target.name }}</span>
                        </button>
                    </div>
                </div>

                <!-- Export Result -->
                <div v-if="exportResult" class="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                    <div class="flex items-center gap-2 mb-2">
                        <CheckCircle class="w-4 h-4 text-green-500" />
                        <span class="text-green-500 font-bold text-sm">Export Successful</span>
                    </div>
                    <div class="text-xs text-gray-400 space-y-1">
                        <div>Generated {{ exportResult.artifacts?.length || 0 }} artifacts</div>
                        <div v-for="artifact in exportResult.artifacts" :key="artifact.name"
                             class="font-mono text-gray-500">
                            - {{ artifact.name }} ({{ artifact.artifact_type }})
                        </div>
                    </div>
                </div>
            </div>
            <div class="p-6 bg-[#141414] flex justify-end gap-3 border-t border-[#222]">
                <button @click="showExportModal = false" class="text-xs font-bold text-gray-500 uppercase px-4 py-2 hover:text-white transition-colors">Close</button>
                <button @click="runExport" :disabled="exporting" class="btn btn-primary">
                    <Download class="w-4 h-4 mr-2" :class="exporting ? 'animate-bounce' : ''" />
                    {{ exporting ? 'Exporting...' : 'Generate' }}
                </button>
            </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
.btn {
  @apply px-4 py-2 rounded font-medium transition-colors duration-200 flex items-center justify-center;
}
.btn-primary {
  @apply bg-orange-600 text-white hover:bg-orange-700;
}
.btn-secondary {
  @apply border border-[#30363d] text-gray-300 hover:text-white hover:bg-[#161b22];
}
</style>
