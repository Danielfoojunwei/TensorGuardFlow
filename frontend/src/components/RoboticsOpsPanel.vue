<script setup>
import { ref, onMounted, computed, onUnmounted } from 'vue'
import {
    Radio, RefreshCw, CheckCircle, XCircle, AlertTriangle,
    ArrowDownCircle, ArrowUpCircle, Activity, Settings,
    RotateCcw, Pause, Play, AlertOctagon, Eye, Clock,
    ChevronRight, Inbox, Send, Shield
} from 'lucide-vue-next'

const status = ref(null)
const loading = ref(true)
const error = ref(null)
const recentEvents = ref([])
const recentSignals = ref([])
const dlqStatus = ref(null)
const selectedProvider = ref(null)
const showRetryModal = ref(false)
const retrying = ref(false)
const refreshInterval = ref(null)

const providers = ['inorbit', 'formant', 'foxglove']

const providerIcons = {
    inorbit: Radio,
    formant: Activity,
    foxglove: Eye
}

const providerColors = {
    inorbit: { bg: 'bg-blue-500/10', text: 'text-blue-500', border: 'border-blue-500/30' },
    formant: { bg: 'bg-green-500/10', text: 'text-green-500', border: 'border-green-500/30' },
    foxglove: { bg: 'bg-purple-500/10', text: 'text-purple-500', border: 'border-purple-500/30' }
}

const statusColors = {
    OK: 'text-green-500',
    WARN: 'text-yellow-500',
    FAIL: 'text-red-500',
    UNKNOWN: 'text-gray-500',
    DISABLED: 'text-gray-600'
}

const severityColors = {
    INFO: 'bg-blue-500/20 text-blue-400',
    WARN: 'bg-yellow-500/20 text-yellow-400',
    CRITICAL: 'bg-red-500/20 text-red-400'
}

const actionIcons = {
    rollback_route: RotateCcw,
    freeze_route: Pause,
    unfreeze_route: Play,
    quarantine_adapter: AlertOctagon,
    open_investigation: Eye,
    acknowledge: CheckCircle,
    no_action: Activity
}

const fetchStatus = async () => {
    try {
        const res = await fetch('/api/v1/robotics/status')
        if (res.ok) {
            status.value = await res.json()
        } else {
            error.value = 'Failed to fetch robotics status'
        }
    } catch (e) {
        console.error("Failed to fetch status", e)
        error.value = e.message
    }
    loading.value = false
}

const fetchRecentEvents = async () => {
    try {
        const res = await fetch('/api/v1/robotics/events/recent?limit=20')
        if (res.ok) {
            const data = await res.json()
            recentEvents.value = data.events || []
        }
    } catch (e) {
        console.error("Failed to fetch recent events", e)
    }
}

const fetchRecentSignals = async () => {
    try {
        const res = await fetch('/api/v1/robotics/signals/recent?limit=20')
        if (res.ok) {
            const data = await res.json()
            recentSignals.value = data.signals || []
        }
    } catch (e) {
        console.error("Failed to fetch recent signals", e)
    }
}

const fetchDLQ = async () => {
    try {
        const res = await fetch('/api/v1/robotics/dlq')
        if (res.ok) {
            dlqStatus.value = await res.json()
        }
    } catch (e) {
        console.error("Failed to fetch DLQ", e)
    }
}

const refreshAll = async () => {
    loading.value = true
    await Promise.all([
        fetchStatus(),
        fetchRecentEvents(),
        fetchRecentSignals(),
        fetchDLQ()
    ])
    loading.value = false
}

const retryDLQ = async () => {
    retrying.value = true
    try {
        const res = await fetch('/api/v1/robotics/dlq/retry', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        if (res.ok) {
            await fetchDLQ()
            showRetryModal.value = false
        } else {
            alert('Retry failed')
        }
    } catch (e) {
        console.error("Retry failed", e)
        alert('Retry failed: ' + e.message)
    }
    retrying.value = false
}

const healthySummary = computed(() => {
    if (!status.value) return { enabled: 0, healthy: 0 }
    return {
        enabled: status.value.summary?.enabled_providers || 0,
        healthy: status.value.summary?.healthy_providers || 0
    }
})

const dlqWarning = computed(() => {
    return (dlqStatus.value?.total_count || 0) > 0
})

const formatTime = (isoString) => {
    if (!isoString) return '-'
    const date = new Date(isoString)
    return date.toLocaleTimeString()
}

const formatDate = (isoString) => {
    if (!isoString) return '-'
    const date = new Date(isoString)
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
}

onMounted(() => {
    refreshAll()
    // Auto-refresh every 30 seconds
    refreshInterval.value = setInterval(refreshAll, 30000)
})

onUnmounted(() => {
    if (refreshInterval.value) {
        clearInterval(refreshInterval.value)
    }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-[#333] pb-6">
       <div>
         <h2 class="text-2xl font-bold flex items-center gap-3">
             <Radio class="w-7 h-7 text-blue-500" />
             Robotics Ops Integrations
         </h2>
         <span class="text-xs text-gray-500">InOrbit / Formant / Foxglove - Ops Loop Connectivity</span>
       </div>
       <div class="flex gap-2">
           <button @click="refreshAll" :disabled="loading" class="btn btn-secondary">
               <RefreshCw class="w-4 h-4" :class="loading ? 'animate-spin' : ''" />
           </button>
       </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading && !status" class="flex justify-center py-12">
        <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
        <XCircle class="w-8 h-8 text-red-500 mx-auto mb-2" />
        <p class="text-red-500">{{ error }}</p>
        <button @click="refreshAll" class="mt-4 btn btn-secondary">Retry</button>
    </div>

    <!-- Main Content -->
    <div v-else class="space-y-6">
        <!-- Health Summary Row -->
        <div class="grid grid-cols-4 gap-4">
            <!-- Overall Status -->
            <div class="bg-[#111] border border-[#333] rounded-lg p-4">
                <div class="flex items-center gap-3">
                    <div :class="['w-10 h-10 rounded-full flex items-center justify-center',
                                  healthySummary.healthy === healthySummary.enabled ? 'bg-green-500/20' : 'bg-yellow-500/20']">
                        <Activity class="w-5 h-5" :class="healthySummary.healthy === healthySummary.enabled ? 'text-green-500' : 'text-yellow-500'" />
                    </div>
                    <div>
                        <div class="text-sm text-gray-500">Providers</div>
                        <div class="text-lg font-semibold">
                            {{ healthySummary.healthy }}/{{ healthySummary.enabled }} Healthy
                        </div>
                    </div>
                </div>
            </div>

            <!-- Outbound Events -->
            <div class="bg-[#111] border border-[#333] rounded-lg p-4">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
                        <ArrowUpCircle class="w-5 h-5 text-blue-500" />
                    </div>
                    <div>
                        <div class="text-sm text-gray-500">Outbound Events</div>
                        <div class="text-lg font-semibold">{{ recentEvents.length }}</div>
                    </div>
                </div>
            </div>

            <!-- Inbound Signals -->
            <div class="bg-[#111] border border-[#333] rounded-lg p-4">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center">
                        <ArrowDownCircle class="w-5 h-5 text-purple-500" />
                    </div>
                    <div>
                        <div class="text-sm text-gray-500">Inbound Signals</div>
                        <div class="text-lg font-semibold">{{ recentSignals.length }}</div>
                    </div>
                </div>
            </div>

            <!-- DLQ Status -->
            <div :class="['bg-[#111] border rounded-lg p-4', dlqWarning ? 'border-yellow-500/50' : 'border-[#333]']">
                <div class="flex items-center gap-3">
                    <div :class="['w-10 h-10 rounded-full flex items-center justify-center',
                                  dlqWarning ? 'bg-yellow-500/20' : 'bg-gray-500/20']">
                        <Inbox class="w-5 h-5" :class="dlqWarning ? 'text-yellow-500' : 'text-gray-500'" />
                    </div>
                    <div class="flex-1">
                        <div class="text-sm text-gray-500">DLQ Depth</div>
                        <div class="text-lg font-semibold">{{ dlqStatus?.total_count || 0 }}</div>
                    </div>
                    <button v-if="dlqWarning" @click="showRetryModal = true" class="btn btn-xs btn-warning">
                        Retry
                    </button>
                </div>
            </div>
        </div>

        <!-- Provider Cards -->
        <div class="grid grid-cols-3 gap-4">
            <div v-for="provider in providers" :key="provider"
                 :class="['bg-[#111] border rounded-lg p-4 cursor-pointer hover:border-[#444] transition-colors',
                          selectedProvider === provider ? providerColors[provider].border : 'border-[#333]']"
                 @click="selectedProvider = selectedProvider === provider ? null : provider">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <component :is="providerIcons[provider]" class="w-5 h-5" :class="providerColors[provider].text" />
                        <span class="font-semibold capitalize">{{ provider }}</span>
                    </div>
                    <span :class="['text-xs px-2 py-0.5 rounded',
                                   status?.providers?.[provider]?.status === 'OK' ? 'bg-green-500/20 text-green-400' :
                                   status?.providers?.[provider]?.status === 'WARN' ? 'bg-yellow-500/20 text-yellow-400' :
                                   status?.providers?.[provider]?.enabled ? 'bg-red-500/20 text-red-400' : 'bg-gray-500/20 text-gray-400']">
                        {{ status?.providers?.[provider]?.status || 'DISABLED' }}
                    </span>
                </div>

                <div v-if="status?.providers?.[provider]?.enabled" class="space-y-2 text-sm text-gray-400">
                    <div class="flex justify-between">
                        <span>Last Outbound:</span>
                        <span>{{ formatTime(status?.providers?.[provider]?.last_outbound?.timestamp) }}</span>
                    </div>
                    <div class="flex justify-between">
                        <span>Last Inbound:</span>
                        <span>{{ formatTime(status?.providers?.[provider]?.last_inbound?.timestamp) }}</span>
                    </div>
                    <div class="flex justify-between">
                        <span>DLQ:</span>
                        <span :class="status?.providers?.[provider]?.dlq_depth > 0 ? 'text-yellow-400' : ''">
                            {{ status?.providers?.[provider]?.dlq_depth || 0 }}
                        </span>
                    </div>
                </div>

                <div v-else class="text-sm text-gray-500">
                    Not configured
                </div>

                <!-- Expanded Details -->
                <div v-if="selectedProvider === provider && status?.providers?.[provider]?.capabilities"
                     class="mt-4 pt-4 border-t border-[#333]">
                    <div class="text-xs text-gray-500 mb-2">Capabilities</div>
                    <div class="flex flex-wrap gap-1">
                        <span v-if="status?.providers?.[provider]?.capabilities?.supports_events_out"
                              class="px-2 py-0.5 bg-blue-500/10 text-blue-400 text-xs rounded">
                            Events Out
                        </span>
                        <span v-if="status?.providers?.[provider]?.capabilities?.supports_webhooks_in"
                              class="px-2 py-0.5 bg-purple-500/10 text-purple-400 text-xs rounded">
                            Webhooks In
                        </span>
                        <span v-if="status?.providers?.[provider]?.capabilities?.supports_incident_create"
                              class="px-2 py-0.5 bg-orange-500/10 text-orange-400 text-xs rounded">
                            Incidents
                        </span>
                        <span v-if="status?.providers?.[provider]?.capabilities?.supports_mcap_export"
                              class="px-2 py-0.5 bg-green-500/10 text-green-400 text-xs rounded">
                            MCAP Export
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Recent Activity Tabs -->
        <div class="bg-[#111] border border-[#333] rounded-lg">
            <div class="flex border-b border-[#333]">
                <button class="px-4 py-3 text-sm font-medium border-b-2 border-blue-500 text-blue-500">
                    <ArrowUpCircle class="w-4 h-4 inline mr-2" />
                    Outbound Events
                </button>
                <button class="px-4 py-3 text-sm font-medium text-gray-500 hover:text-gray-300">
                    <ArrowDownCircle class="w-4 h-4 inline mr-2" />
                    Inbound Signals
                </button>
            </div>

            <!-- Outbound Events List -->
            <div class="max-h-64 overflow-y-auto">
                <table class="w-full text-sm">
                    <thead class="bg-[#0a0a0a] sticky top-0">
                        <tr class="text-gray-500 text-xs uppercase">
                            <th class="px-4 py-2 text-left">Time</th>
                            <th class="px-4 py-2 text-left">Type</th>
                            <th class="px-4 py-2 text-left">Severity</th>
                            <th class="px-4 py-2 text-left">Provider</th>
                            <th class="px-4 py-2 text-left">Status</th>
                            <th class="px-4 py-2 text-left">Latency</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="event in recentEvents" :key="event.event_id"
                            class="border-t border-[#222] hover:bg-[#1a1a1a]">
                            <td class="px-4 py-2 text-gray-400">{{ formatTime(event.timestamp) }}</td>
                            <td class="px-4 py-2">
                                <span class="text-xs font-mono bg-[#222] px-2 py-0.5 rounded">
                                    {{ event.type }}
                                </span>
                            </td>
                            <td class="px-4 py-2">
                                <span :class="['text-xs px-2 py-0.5 rounded', severityColors[event.severity]]">
                                    {{ event.severity }}
                                </span>
                            </td>
                            <td class="px-4 py-2 text-gray-400 capitalize">{{ event.provider }}</td>
                            <td class="px-4 py-2">
                                <CheckCircle v-if="event.success" class="w-4 h-4 text-green-500" />
                                <XCircle v-else class="w-4 h-4 text-red-500" />
                            </td>
                            <td class="px-4 py-2 text-gray-400">{{ event.latency_ms }}ms</td>
                        </tr>
                        <tr v-if="recentEvents.length === 0">
                            <td colspan="6" class="px-4 py-8 text-center text-gray-500">
                                No recent outbound events
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Inbound Signals Section -->
        <div class="bg-[#111] border border-[#333] rounded-lg">
            <div class="px-4 py-3 border-b border-[#333] flex items-center justify-between">
                <h3 class="font-semibold flex items-center gap-2">
                    <ArrowDownCircle class="w-5 h-5 text-purple-500" />
                    Recent Inbound Signals
                </h3>
                <span class="text-xs text-gray-500">Last 20 signals</span>
            </div>

            <div class="max-h-64 overflow-y-auto">
                <table class="w-full text-sm">
                    <thead class="bg-[#0a0a0a] sticky top-0">
                        <tr class="text-gray-500 text-xs uppercase">
                            <th class="px-4 py-2 text-left">Time</th>
                            <th class="px-4 py-2 text-left">Source</th>
                            <th class="px-4 py-2 text-left">Type</th>
                            <th class="px-4 py-2 text-left">Severity</th>
                            <th class="px-4 py-2 text-left">Route</th>
                            <th class="px-4 py-2 text-left">Action Taken</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="signal in recentSignals" :key="signal.signal_id"
                            class="border-t border-[#222] hover:bg-[#1a1a1a]">
                            <td class="px-4 py-2 text-gray-400">{{ formatTime(signal.timestamp) }}</td>
                            <td class="px-4 py-2">
                                <span :class="['text-xs px-2 py-0.5 rounded capitalize', providerColors[signal.source?.toLowerCase()]?.bg || 'bg-gray-500/20']">
                                    {{ signal.source }}
                                </span>
                            </td>
                            <td class="px-4 py-2">
                                <span class="text-xs font-mono bg-[#222] px-2 py-0.5 rounded">
                                    {{ signal.type }}
                                </span>
                            </td>
                            <td class="px-4 py-2">
                                <span :class="['text-xs px-2 py-0.5 rounded', severityColors[signal.severity]]">
                                    {{ signal.severity }}
                                </span>
                            </td>
                            <td class="px-4 py-2 text-gray-400 font-mono text-xs">{{ signal.route_key }}</td>
                            <td class="px-4 py-2">
                                <span v-if="signal.action_taken" class="flex items-center gap-1 text-xs">
                                    <component :is="actionIcons[signal.action_taken] || Activity" class="w-3 h-3" />
                                    {{ signal.action_taken?.replace('_', ' ') }}
                                </span>
                                <span v-else class="text-gray-500 text-xs">-</span>
                            </td>
                        </tr>
                        <tr v-if="recentSignals.length === 0">
                            <td colspan="6" class="px-4 py-8 text-center text-gray-500">
                                No recent inbound signals
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- DLQ Warning Banner -->
        <div v-if="dlqWarning" class="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <AlertTriangle class="w-5 h-5 text-yellow-500" />
                    <div>
                        <div class="font-semibold text-yellow-400">Dead Letter Queue Has Entries</div>
                        <div class="text-sm text-gray-400">
                            {{ dlqStatus?.total_count }} events failed delivery
                            ({{ dlqStatus?.failed_permanently }} permanently failed)
                        </div>
                    </div>
                </div>
                <button @click="showRetryModal = true" class="btn btn-warning">
                    <RotateCcw class="w-4 h-4 mr-2" />
                    Retry All
                </button>
            </div>
        </div>
    </div>

    <!-- Retry Modal -->
    <div v-if="showRetryModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-[#111] border border-[#333] rounded-lg p-6 max-w-md w-full mx-4">
            <h3 class="text-lg font-semibold mb-4">Retry Failed Deliveries</h3>
            <p class="text-gray-400 mb-4">
                This will retry delivery for {{ dlqStatus?.total_count }} entries in the dead letter queue.
            </p>
            <div class="flex justify-end gap-2">
                <button @click="showRetryModal = false" class="btn btn-secondary">Cancel</button>
                <button @click="retryDLQ" :disabled="retrying" class="btn btn-primary">
                    <RefreshCw v-if="retrying" class="w-4 h-4 mr-2 animate-spin" />
                    Retry Now
                </button>
            </div>
        </div>
    </div>
  </div>
</template>
