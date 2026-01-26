<script setup>
/**
 * Models Workbench - Unified Model Lifecycle Management
 *
 * Consolidates: VLA Registry, PEFT Studio, Eval Arena, Skills Library, Model Lineage
 * Tabbed interface for complete model workflow from creation to deployment
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
    Bot, Database, Scale, BookOpen, GitBranch,
    Plus, Search, Filter, RefreshCw, Play, Shield,
    Rocket, Eye, CheckCircle, Clock, AlertTriangle,
    ChevronDown, Settings2, TrendingUp, Zap, RotateCcw,
    Sliders
} from 'lucide-vue-next'
import ModelGating from './ModelGating.vue'

const props = defineProps({
    initialTab: { type: String, default: 'registry' }
})

const router = useRouter()
const route = useRoute()

const activeTab = ref(route.params.tab || props.initialTab)

// Sync with route params
watch(() => route.params.tab, (newTab) => {
    if (newTab && newTab !== activeTab.value) {
        activeTab.value = newTab
    }
})

// Update route when tab changes
const setActiveTab = (tabId) => {
    activeTab.value = tabId
    router.push(`/models/${tabId}`)
}

const tabs = [
    { id: 'registry', label: 'Model Registry', icon: Bot, description: 'VLA models & deployment' },
    { id: 'training', label: 'Training', icon: Database, description: 'PEFT fine-tuning runs' },
    { id: 'evaluation', label: 'Evaluation', icon: Scale, description: 'Benchmarks & testing' },
    { id: 'skills', label: 'Skills Library', icon: BookOpen, description: 'FedMoE experts' },
    { id: 'lineage', label: 'Lineage', icon: GitBranch, description: 'Version history' }
]

// Shared state across tabs
const models = ref([])
const trainingRuns = ref([])
const skills = ref([])
const loading = ref(true)
const searchQuery = ref('')
const statusFilter = ref('all')
const errorMessage = ref('')

// Modal states
const showCreateModal = ref(false)
const showDeployModal = ref(false)
const showEvalModal = ref(false)
const selectedModel = ref(null)
const selectedEvalModel = ref('')
const configuringExpert = ref(null)

// Fetch data
const fetchData = async () => {
    loading.value = true
    errorMessage.value = ''
    try {
        const [modelsRes, runsRes, skillsRes] = await Promise.allSettled([
            fetch('/api/v1/vla/models'),
            fetch('/api/v1/peft/runs'),
            fetch('/api/v1/fedmoe/skills-library')
        ])

        if (modelsRes.status === 'fulfilled' && modelsRes.value.ok) {
            const data = await modelsRes.value.json()
            models.value = data.models || []
        } else {
            models.value = []
            errorMessage.value = 'Unable to load models. Verify API connectivity.'
        }

        if (runsRes.status === 'fulfilled' && runsRes.value.ok) {
            trainingRuns.value = await runsRes.value.json()
        } else {
            trainingRuns.value = []
            if (!errorMessage.value) {
                errorMessage.value = 'Unable to load training runs. Verify API connectivity.'
            }
        }

        if (skillsRes.status === 'fulfilled' && skillsRes.value.ok) {
            skills.value = await skillsRes.value.json()
        } else {
            skills.value = []
            if (!errorMessage.value) {
                errorMessage.value = 'Unable to load skills library. Verify API connectivity.'
            }
        }
    } catch (e) {
        console.error('Failed to fetch data', e)
        models.value = []
        trainingRuns.value = []
        skills.value = []
        errorMessage.value = 'Unable to load model data. Verify API connectivity.'
    }
    loading.value = false
}

// Filtered data
const filteredModels = computed(() => {
    return models.value.filter(m => {
        const matchesSearch = m.name.toLowerCase().includes(searchQuery.value.toLowerCase())
        const matchesStatus = statusFilter.value === 'all' || m.status === statusFilter.value
        return matchesSearch && matchesStatus
    })
})

// Status helpers
const getStatusStyle = (status) => {
    const styles = {
        deployed: 'bg-green-500/10 text-green-500 border-green-500/30',
        staged: 'bg-blue-500/10 text-blue-500 border-blue-500/30',
        validating: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/30',
        running: 'bg-blue-500/10 text-blue-500 border-blue-500/30',
        completed: 'bg-green-500/10 text-green-500 border-green-500/30',
        failed: 'bg-red-500/10 text-red-500 border-red-500/30',
        validated: 'bg-green-500/10 text-green-500 border-green-500/30',
        adapting: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/30'
    }
    return styles[status] || 'bg-gray-500/10 text-gray-500 border-gray-500/30'
}

// Actions
const startTraining = () => {
    setActiveTab('training')
    // Open training wizard
}

const deployModel = (model) => {
    selectedModel.value = model
    showDeployModal.value = true
}

const runValidation = async (modelId) => {
    try {
        await fetch('/api/v1/vla/safety/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_id: modelId, test_environment: 'production', test_scenarios: 100 })
        })
        await fetchData()
    } catch (e) {
        console.error('Validation failed', e)
    }
}

onMounted(fetchData)
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Header with Tabs -->
    <div class="flex-shrink-0 border-b border-[#30363d] bg-[#0d1117]">
      <div class="px-6 pt-4">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h1 class="text-xl font-bold text-white">Models</h1>
            <p class="text-xs text-gray-500">Model lifecycle from training to deployment</p>
          </div>
          <div class="flex items-center gap-3">
            <button @click="fetchData" class="p-2 rounded hover:bg-[#1f2428] transition-colors">
              <RefreshCw class="w-4 h-4 text-gray-400" :class="loading ? 'animate-spin' : ''" />
            </button>
            <button @click="showCreateModal = true"
                    class="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium flex items-center gap-2 transition-colors">
              <Plus class="w-4 h-4" /> New Model
            </button>
          </div>
        </div>

        <!-- Tabs -->
        <div class="flex gap-1">
          <button v-for="tab in tabs" :key="tab.id"
                  :data-testid="`models-tab-${tab.id}`"
                  @click="setActiveTab(tab.id)"
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
      <div v-if="errorMessage" class="px-6 py-3 text-xs text-red-400 bg-red-500/10 border-b border-red-500/30">
        {{ errorMessage }}
      </div>
      <!-- Registry Tab -->
      <div v-if="activeTab === 'registry'" class="h-full overflow-y-auto p-6">
        <!-- Filters -->
        <div class="flex items-center gap-4 mb-6">
          <div class="flex-1 relative">
            <Search class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input v-model="searchQuery" type="text" placeholder="Search models..."
                   class="w-full bg-[#0d1117] border border-[#30363d] rounded-lg pl-10 pr-4 py-2 text-sm focus:border-primary/50 focus:outline-none" />
          </div>
          <select v-model="statusFilter"
                  class="bg-[#0d1117] border border-[#30363d] rounded-lg px-4 py-2 text-sm focus:outline-none cursor-pointer">
            <option value="all">All Status</option>
            <option value="deployed">Deployed</option>
            <option value="staged">Staged</option>
            <option value="validating">Validating</option>
          </select>
        </div>

        <!-- Model Cards -->
        <div class="space-y-4">
          <div v-for="model in filteredModels" :key="model.id"
               class="bg-[#0d1117] border border-[#30363d] rounded-lg p-5 hover:border-[#484f58] transition-colors">
            <div class="flex items-start justify-between mb-4">
              <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-lg bg-gradient-to-br from-primary/20 to-purple-500/20 border border-primary/30 flex items-center justify-center">
                  <Bot class="w-6 h-6 text-primary" />
                </div>
                <div>
                  <div class="flex items-center gap-2">
                    <h3 class="font-semibold text-white">{{ model.name }}</h3>
                    <span class="text-xs font-mono text-gray-500">v{{ model.version }}</span>
                  </div>
                  <div class="flex items-center gap-2 mt-1">
                    <span :class="['text-[10px] font-bold uppercase px-2 py-0.5 rounded border', getStatusStyle(model.status)]">
                      {{ model.status }}
                    </span>
                    <span class="text-xs text-gray-500">{{ model.id }}</span>
                  </div>
                </div>
              </div>

              <div class="flex items-center gap-2">
                <button v-if="model.status === 'staged'" @click="runValidation(model.id)"
                        class="px-3 py-1.5 text-xs bg-purple-600 hover:bg-purple-700 text-white rounded flex items-center gap-1.5 transition-colors">
                  <Shield class="w-3 h-3" /> Validate
                </button>
                <button v-if="model.status === 'staged' && model.safety_score >= 0.8" @click="deployModel(model)"
                        class="px-3 py-1.5 text-xs bg-primary hover:bg-primary/90 text-white rounded flex items-center gap-1.5 transition-colors">
                  <Rocket class="w-3 h-3" /> Deploy
                </button>
                <button class="p-1.5 hover:bg-[#1f2428] rounded transition-colors">
                  <Eye class="w-4 h-4 text-gray-400" />
                </button>
              </div>
            </div>

            <!-- Task Types -->
            <div class="flex flex-wrap gap-2 mb-4">
              <span v-for="task in model.task_types" :key="task"
                    class="text-[10px] font-mono px-2 py-1 rounded bg-[#1f2428] text-gray-300 border border-[#30363d]">
                {{ task }}
              </span>
            </div>

            <!-- Metrics Row -->
            <div class="grid grid-cols-3 gap-4">
              <div class="bg-[#161b22] p-3 rounded border border-[#30363d]">
                <div class="text-[10px] text-gray-500 uppercase mb-1">Success Rate</div>
                <div class="text-lg font-bold text-green-500">{{ (model.success_rate * 100).toFixed(1) }}%</div>
              </div>
              <div class="bg-[#161b22] p-3 rounded border border-[#30363d]">
                <div class="text-[10px] text-gray-500 uppercase mb-1">Safety Score</div>
                <div class="text-lg font-bold" :class="model.safety_score ? 'text-purple-500' : 'text-gray-500'">
                  {{ model.safety_score ? (model.safety_score * 100).toFixed(0) + '%' : 'N/A' }}
                </div>
              </div>
              <div class="bg-[#161b22] p-3 rounded border border-[#30363d]">
                <div class="text-[10px] text-gray-500 uppercase mb-1">Created</div>
                <div class="text-sm font-medium text-gray-300">{{ model.created_at?.split('T')[0] }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Training Tab -->
      <div v-else-if="activeTab === 'training'" class="h-full overflow-y-auto p-6">
        <div class="max-w-4xl mx-auto">
          <div class="flex items-center justify-between mb-6">
            <h2 class="text-lg font-semibold text-white">Training Runs</h2>
            <button class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors">
              <Play class="w-4 h-4" /> Start New Run
            </button>
          </div>

          <div class="space-y-4">
            <div v-for="run in trainingRuns" :key="run.id"
                 class="bg-[#0d1117] border border-[#30363d] rounded-lg p-5">
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-3">
                  <Database class="w-5 h-5 text-blue-500" />
                  <div>
                    <div class="font-semibold text-white">{{ run.name }}</div>
                    <div class="text-xs text-gray-500">Base: {{ run.model }}</div>
                  </div>
                </div>
                <span :class="['text-xs font-bold uppercase px-2 py-1 rounded border', getStatusStyle(run.status)]">
                  {{ run.status }}
                </span>
              </div>

              <div v-if="run.status === 'running'" class="mb-3">
                <div class="flex justify-between text-xs text-gray-500 mb-1">
                  <span>Progress</span>
                  <span>{{ run.progress }}%</span>
                </div>
                <div class="h-2 bg-[#30363d] rounded-full overflow-hidden">
                  <div class="h-full bg-blue-500 transition-all" :style="{ width: run.progress + '%' }"></div>
                </div>
              </div>

              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>Started: {{ run.created_at?.split('T')[0] }}</span>
                <button class="text-primary hover:text-primary/80">View Details</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Evaluation Tab -->
      <div v-else-if="activeTab === 'evaluation'" class="h-full overflow-y-auto p-6">
        <div class="max-w-5xl mx-auto">
          <div class="text-center py-12">
            <Scale class="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <h2 class="text-lg font-semibold text-white mb-2">Evaluation Arena</h2>
            <p class="text-gray-500 mb-6">Run benchmarks and compare model performance</p>
            <button @click="showEvalModal = true" class="px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium">
              Start Evaluation
            </button>
          </div>
        </div>
      </div>

      <!-- Skills Tab -->
      <div v-else-if="activeTab === 'skills'" class="h-full overflow-y-auto p-6">
        <div class="space-y-4">
          <div v-for="skill in skills" :key="skill.id"
               class="bg-[#0d1117] border border-[#30363d] rounded-lg p-5">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <BookOpen class="w-5 h-5 text-purple-500" />
                <div>
                  <div class="font-semibold text-white">{{ skill.name }}</div>
                  <div class="text-xs text-gray-500">Base: {{ skill.base_model }}</div>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <div class="text-right">
                  <div class="text-lg font-bold text-green-500">{{ (skill.accuracy * 100).toFixed(0) }}%</div>
                  <div class="text-[10px] text-gray-500">accuracy</div>
                </div>
                <span :class="['text-xs font-bold uppercase px-2 py-1 rounded border', getStatusStyle(skill.status)]">
                  {{ skill.status }}
                </span>
                <button @click="configuringExpert = configuringExpert?.id === skill.id ? null : skill"
                        class="p-2 rounded hover:bg-[#1f2428] transition-colors"
                        title="Configure Gating">
                  <Sliders class="w-4 h-4 text-gray-400" :class="configuringExpert?.id === skill.id ? 'text-primary' : ''" />
                </button>
              </div>
            </div>

            <!-- Inline Gating Control -->
            <div v-if="configuringExpert?.id === skill.id" class="mt-4 border-t border-[#30363d] pt-4 animate-in slide-in-from-top-2 duration-300">
               <ModelGating :expert="skill" @updated="fetchData" />
            </div>
          </div>
        </div>
        </div>

    <!-- New Model Modal -->
    <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div class="bg-[#0d1117] border border-[#30363d] rounded-xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-200">
        <div class="px-6 py-4 border-b border-[#30363d] flex items-center justify-between bg-[#161b22]">
          <h3 class="font-bold text-white">Create New VLA Model</h3>
          <button @click="showCreateModal = false" class="text-gray-500 hover:text-white transition-colors">
            <Plus class="w-5 h-5 rotate-45" />
          </button>
        </div>
        <div class="p-6 space-y-4">
          <div class="space-y-1">
            <label class="text-[10px] font-bold text-gray-500 uppercase">Model Name</label>
            <input type="text" placeholder="e.g. humanoid-grasping-pro" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white focus:border-primary/50 outline-none" />
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-1">
              <label class="text-[10px] font-bold text-gray-500 uppercase">Base Architecture</label>
              <select class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white">
                <option>Llama-3-8B-VLA</option>
                <option>OpenVLA-7B</option>
                <option>I-VLA-Base</option>
              </select>
            </div>
            <div class="space-y-1">
              <label class="text-[10px] font-bold text-gray-500 uppercase">Version</label>
              <input type="text" value="1.0.0" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white" disabled />
            </div>
          </div>
          <div class="p-4 bg-primary/5 border border-primary/20 rounded-lg">
            <div class="flex items-center gap-2 text-primary mb-1">
              <Shield class="w-4 h-4" />
              <span class="text-xs font-bold uppercase">PQC Protection Active</span>
            </div>
            <p class="text-[11px] text-gray-400">All GA models require Dilithium-3 signatures for weight integrity verification at the edge node.</p>
          </div>
        </div>
        <div class="px-6 py-4 bg-[#161b22] border-t border-[#30363d] flex justify-end gap-3">
          <button @click="showCreateModal = false" class="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white transition-colors">Cancel</button>
          <button @click="showCreateModal = false" class="px-4 py-2 bg-primary text-white text-sm font-bold rounded hover:bg-primary/90 transition-colors">Initialize Model</button>
        </div>
      </div>
    </div>

    <!-- Deploy Model Modal -->
    <div v-if="showDeployModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div class="bg-[#0d1117] border border-[#30363d] rounded-xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-200">
        <div class="px-6 py-4 border-b border-[#30363d] flex items-center justify-between bg-[#161b22]">
          <h3 class="font-bold text-white">Deploy: {{ selectedModel?.name }}</h3>
          <button @click="showDeployModal = false" class="text-gray-500 hover:text-white transition-colors">
            <Plus class="w-5 h-5 rotate-45" />
          </button>
        </div>
        <div class="p-6 space-y-4">
          <div class="space-y-1">
            <label class="text-[10px] font-bold text-gray-500 uppercase">Target Fleet</label>
            <select class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white">
              <option>Production-US-West (24 nodes)</option>
              <option>Staging-Laboratory (5 nodes)</option>
              <option>Canary-Fleet-7 (2 nodes)</option>
            </select>
          </div>
          <div class="space-y-1">
            <label class="text-[10px] font-bold text-gray-500 uppercase">Rollout Strategy</label>
            <div class="grid grid-cols-3 gap-2">
              <button class="p-2 border border-primary/50 bg-primary/10 rounded text-[10px] font-bold text-white">IMMEDIATE</button>
              <button class="p-2 border border-[#30363d] hover:border-gray-500 rounded text-[10px] font-bold text-gray-400 transition-colors">CANARY (10%)</button>
              <button class="p-2 border border-[#30363d] hover:border-gray-500 rounded text-[10px] font-bold text-gray-400 transition-colors">BLUE/GREEN</button>
            </div>
          </div>
          <div class="flex items-center gap-3 p-3 bg-yellow-500/5 border border-yellow-500/20 rounded-md">
            <AlertTriangle class="w-5 h-5 text-yellow-500 shrink-0" />
            <div class="text-[11px] text-yellow-500/80">
              GA Safeguard: Ensure this model has completed a 1000-cycle simulation benchmark before production deployment.
            </div>
          </div>
        </div>
        <div class="px-6 py-4 bg-[#161b22] border-t border-[#30363d] flex justify-end gap-3">
          <button @click="showDeployModal = false" class="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white transition-colors">Cancel</button>
          <button @click="showDeployModal = false" class="px-4 py-2 bg-orange-600 text-white text-sm font-bold rounded hover:bg-orange-700 transition-colors">Push to Edge</button>
        </div>
      </div>
    </div>

      <!-- Lineage Tab -->
      <div v-else-if="activeTab === 'lineage'" class="h-full overflow-y-auto p-6">
        <div class="max-w-4xl mx-auto">
          <div class="text-center py-12">
            <GitBranch class="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <h2 class="text-lg font-semibold text-white mb-2">Model Lineage</h2>
            <p class="text-gray-500">Version history and deployment tracking</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Evaluation Modal -->
    <div v-if="showEvalModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div class="bg-[#0d1117] border border-[#30363d] rounded-xl w-full max-w-lg overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-200">
        <div class="px-6 py-4 border-b border-[#30363d] flex items-center justify-between bg-[#161b22]">
          <h3 class="font-bold text-white">Start Benchmark Evaluation</h3>
          <button @click="showEvalModal = false" class="text-gray-500 hover:text-white transition-colors">
            <Plus class="w-5 h-5 rotate-45" />
          </button>
        </div>
        <div class="p-6 space-y-4">
          <div class="space-y-1">
            <label class="text-[10px] font-bold text-gray-500 uppercase">Target Model</label>
            <select v-model="selectedEvalModel" class="w-full bg-[#161b22] border border-[#30363d] rounded p-2 text-sm text-white focus:border-primary/50 outline-none">
              <option v-for="m in models" :key="m.id" :value="m.id">{{ m.name }} (v{{ m.version }})</option>
              <option value="test">Llama-3-8B-Baseline</option>
            </select>
          </div>
          <div class="space-y-1">
            <label class="text-[10px] font-bold text-gray-500 uppercase">Benchmark Suite</label>
            <div class="grid grid-cols-2 gap-2">
              <button class="p-2 border border-primary/50 bg-primary/10 rounded text-[10px] font-bold text-white text-left">GRASPING_SURROGATE</button>
              <button class="p-2 border border-[#30363d] hover:border-gray-500 rounded text-[10px] font-bold text-gray-400 transition-colors text-left">NAV_OBSTACLE_V3</button>
              <button class="p-2 border border-[#30363d] hover:border-gray-500 rounded text-[10px] font-bold text-gray-400 transition-colors text-left">SIM_H1_ASSEMBLY</button>
              <button class="p-2 border border-[#30363d] hover:border-gray-500 rounded text-[10px] font-bold text-gray-400 transition-colors text-left">LLM_REASONING_PRO</button>
            </div>
          </div>
          <div class="p-3 bg-purple-500/5 border border-purple-500/20 rounded-md flex gap-3">
             <Scale class="w-5 h-5 text-purple-500 shrink-0" />
             <div class="text-[11px] text-gray-400">
                Running an evaluation generates a high-fidelity safety score required for production staging in the v2.3 GA workflow.
             </div>
          </div>
        </div>
        <div class="px-6 py-4 bg-[#161b22] border-t border-[#30363d] flex justify-end gap-3">
          <button @click="showEvalModal = false" class="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white transition-colors">Cancel</button>
          <button @click="showEvalModal = false" class="px-4 py-2 bg-primary text-white text-sm font-bold rounded hover:bg-primary/90 transition-colors">Queue Evaluation</button>
        </div>
      </div>
    </div>

  </div>
</template>
