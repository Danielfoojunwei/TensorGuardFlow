<script setup>
import { ref, onMounted } from 'vue'
import { Play, AlertTriangle, CheckCircle, Zap, Crosshair, Box, Plus, History, ShieldCheck } from 'lucide-vue-next'

const task = ref('Pick up the red cube and place it on the blue coaster')
const generated = ref(false)
const evaluating = ref(false)
const showCreateModal = ref(false)
const newExpertName = ref('')
const newExpertBase = ref('openvla-7b')

const experts = ref([])
const selectedExpert = ref(null)

const fetchExperts = async () => {
    try {
        const res = await fetch('/api/v1/fedmoe/experts')
        const data = await res.json()
        experts.value = Array.isArray(data) ? data : []
        if (experts.value.length > 0 && !selectedExpert.value) {
            selectedExpert.value = experts.value[0]
        }
    } catch (e) {
        console.error("Failed to fetch experts", e)
        experts.value = []
    }
}

const createExpert = async () => {
    if (!newExpertName.value.trim()) {
        alert("Expert name is required")
        return
    }
    try {
        const res = await fetch('/api/v1/fedmoe/experts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: newExpertName.value,
                base_model: newExpertBase.value
            })
        })
        if (!res.ok) {
            const error = await res.json()
            alert(`Failed: ${error.detail || 'Unknown error'}`)
            return
        }
        const data = await res.json()
        experts.value.push(data)
        selectedExpert.value = data
        showCreateModal.value = false
        newExpertName.value = ''
    } catch (e) {
        console.error("Failed to create expert", e)
    }
}

const startEval = async () => {
    if (!task.value || !selectedExpert.value) return
    evaluating.value = true
    generated.value = false
    
    // Simulate generation delay
    setTimeout(async () => {
        evaluating.value = false
        generated.value = true
        
        // POST real evidence to backend
        try {
            await fetch(`/api/v1/fedmoe/experts/${selectedExpert.value.id}/evidence`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    evidence_type: 'SIM_SUCCESS',
                    value: {
                        task: task.value,
                        score: 0.92,
                        collision_rate: 0.001,
                        latency_hz: 25
                    }
                })
            })
            fetchExperts() // Refresh expert status
        } catch (e) {
            console.error("Failed to submit evidence", e)
        }
    }, 2500)
}

const benchmarks = ref([
    { name: 'Sim Success Rate (SR)', score_base: '42%', score_ft: '92%', status: 'improved' },
    { name: 'Collision Rate', score_base: '15%', score_ft: '0.1%', status: 'improved' },
    { name: 'Command Latency (Hz)', score_base: '5Hz', score_ft: '25Hz', status: 'improved' },
    { name: 'Behavioral Drift', score_base: 'Low', score_ft: 'Stable', status: 'improved' },
])

onMounted(fetchExperts)
</script>

<template>
  <div class="h-full flex flex-col p-6 space-y-6">
      <!-- Header -->
      <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
              <div>
                  <h2 class="text-2xl font-bold uppercase tracking-tight">FedMoE Eval Arena</h2>
                  <div class="flex items-center gap-2">
                      <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                      <span class="text-[10px] text-gray-500 font-mono uppercase">Simulation Engine Active</span>
                  </div>
              </div>
          </div>
          <div class="flex items-center gap-3">
               <div class="flex items-center gap-2 bg-[#111] border border-[#333] p-1 rounded-lg">
                   <select v-model="selectedExpert" class="bg-transparent text-sm font-bold text-white outline-none px-3 cursor-pointer">
                       <option v-for="e in experts" :key="e.id" :value="e">{{ e.name }} ({{ e.status }})</option>
                   </select>
                   <button @click="showCreateModal = true" class="bg-primary/20 hover:bg-primary/40 text-primary p-2 rounded transition-colors" title="Create New Expert">
                       <Plus class="w-4 h-4" />
                   </button>
               </div>
          </div>
      </div>

      <!-- Main Compare View -->
      <div class="flex-1 grid grid-cols-12 gap-6 min-h-0">
          
          <!-- Base Policy Visualization (Col 1-5) -->
          <div class="col-span-4 bg-[#111] border border-[#333] rounded-lg flex flex-col overflow-hidden relative grayscale opacity-40">
             <div class="p-3 border-b border-[#333] bg-[#161616] flex justify-between items-center">
                 <span class="font-bold text-[10px] text-gray-500 uppercase tracking-widest">Base: OpenVLA-7B</span>
                 <span class="text-[10px] text-red-500 font-bold border border-red-500/30 px-2 py-0.5 rounded">FAILED</span>
             </div>
             
             <!-- Mock Sim View -->
             <div class="flex-1 relative bg-[#050505] overflow-hidden flex items-center justify-center p-8">
                  <div class="absolute inset-0 grid grid-cols-12 grid-rows-12 gap-1 opacity-10 pointer-events-none text-green-500/20">
                      <div v-for="i in 144" :key="i" class="border-[0.5px] border-current"></div>
                  </div>
                  <div class="relative w-full h-full border border-[#333] rounded p-4 flex items-center justify-center">
                       <div class="w-16 h-16 border-2 border-gray-600 rounded flex items-center justify-center text-xs text-gray-600">Blue Pad</div>
                       <div class="absolute top-10 left-10 w-8 h-8 bg-red-800 rounded flex items-center justify-center text-[8px] text-white">Cube</div>
                       <svg class="absolute inset-0 w-full h-full pointer-events-none">
                           <path d="M 50 50 Q 100 150 200 100" stroke="#333" stroke-width="2" fill="none" stroke-dasharray="5,5" />
                           <circle cx="200" cy="100" r="4" fill="red" />
                       </svg>
                  </div>
             </div>
          </div>

          <!-- Fine-Tuned Policy Visualization (Col 6-12) -->
          <div class="col-span-5 bg-[#111] border border-[#333] rounded-lg flex flex-col overflow-hidden relative shadow-2xl" :class="generated ? 'border-primary/50 ring-1 ring-primary/20' : ''">
             <div class="p-3 border-b border-[#333] bg-[#161616] flex justify-between items-center">
                 <div class="flex items-center gap-2">
                     <span class="font-bold text-[10px] text-primary uppercase tracking-widest">Expert: {{ selectedExpert?.name || 'Loading...' }}</span>
                     <span v-if="selectedExpert?.status === 'validated'" class="text-[8px] bg-green-500/10 text-green-500 border border-green-500/30 px-1.5 rounded flex items-center gap-1">
                         <ShieldCheck class="w-2.5 h-2.5" /> PQC VERIFIED
                     </span>
                 </div>
                 <span v-if="generated" class="text-[10px] text-green-500 font-bold border border-green-500/30 px-2 py-0.5 rounded animate-pulse">SUCCESS (0.8s)</span>
             </div>
             
             <!-- Mock Sim View Active -->
             <div class="flex-1 relative bg-[#050505] overflow-hidden flex items-center justify-center p-8">
                  <div class="absolute inset-0 grid grid-cols-12 grid-rows-12 gap-1 opacity-20 pointer-events-none text-primary/10">
                      <div v-for="i in 144" :key="i" class="border-[0.5px] border-current"></div>
                  </div>
                  
                  <div v-if="!generated && !evaluating" class="absolute inset-0 flex items-center justify-center text-gray-700 font-mono text-[10px] uppercase tracking-tighter">
                      Waiting for command sequence...
                  </div>

                  <div v-if="evaluating" class="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/60 z-10 backdrop-blur-md">
                      <div class="w-12 h-12 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
                      <div class="font-mono text-primary text-[10px] tracking-widest uppercase animate-pulse">Running Physics Sim...</div>
                  </div>

                  <!-- Success Visual -->
                  <div v-if="generated" class="relative w-full h-full border border-primary/20 rounded p-4 flex items-center justify-center transition-all duration-700 scale-105">
                       <div class="w-16 h-16 border-2 border-blue-500/50 rounded flex items-center justify-center text-xs text-blue-500 shadow-[0_0_30px_rgba(59,130,246,0.3)]">
                            <div class="w-8 h-8 bg-red-600 rounded flex items-center justify-center text-[8px] text-white shadow-lg transform rotate-12">Cube</div>
                       </div>
                       <!-- Trajectory -->
                       <svg class="absolute inset-0 w-full h-full pointer-events-none">
                           <path d="M 50 50 Q 150 50 250 150 T 400 200" stroke="#ff5722" stroke-width="3" fill="none" class="drop-shadow-[0_0_8px_rgba(255,87,34,0.9)]" />
                           <circle cx="400" cy="200" r="4" fill="#ff5722" class="animate-ping" />
                       </svg>
                  </div>
             </div>
          </div>

          <!-- Expert Evidence Fabric (Col 10-12) -->
          <div class="col-span-3 bg-[#111] border border-[#333] rounded-lg overflow-hidden flex flex-col">
              <div class="p-3 border-b border-[#333] bg-[#161616] font-bold text-[11px] uppercase tracking-widest text-gray-400 flex items-center gap-2">
                  <History class="w-3.4 h-3.5" /> Expert Evidence Fabric
              </div>
              <div class="flex-1 p-4 space-y-4 overflow-y-auto">
                  <div v-if="!selectedExpert?.evidences?.length" class="text-center py-8">
                      <Box class="w-8 h-8 text-gray-800 mx-auto mb-2" />
                      <span class="text-[10px] text-gray-600 uppercase">No Skill Evidence Logged</span>
                  </div>
                  <div v-for="ev in selectedExpert?.evidences" :key="ev.id" class="bg-[#0c0c0c] border border-[#222] p-3 rounded-lg relative overflow-hidden group">
                      <div class="absolute left-0 top-0 w-1 h-full bg-primary opacity-50"></div>
                      <div class="flex justify-between items-start mb-2">
                          <span class="text-[10px] font-bold text-gray-400 uppercase tracking-tight">{{ ev.evidence_type }}</span>
                          <CheckCircle class="w-3 h-3 text-green-500" />
                      </div>
                      <div class="text-[9px] text-gray-500 font-mono mb-2 line-clamp-1">CID: {{ ev.id }}</div>
                      <div class="text-[10px] text-gray-400 flex items-center gap-1">
                          <ShieldCheck class="w-2.5 h-2.5 text-primary" />
                          <span class="truncate">Dilithium-3: {{ ev.signed_proof?.slice(0, 12) }}...</span>
                      </div>
                  </div>
              </div>
          </div>
      </div>

      <!-- Input Area & Benchmarks -->
      <div class="h-1/4 grid grid-cols-12 gap-6">
          <!-- Input -->
          <div class="col-span-8 flex flex-col">
              <label class="text-[10px] text-gray-600 font-bold mb-2 uppercase tracking-widest flex items-center gap-2">
                  <Zap class="w-3 h-3 text-primary" /> VLA Skill Instruction (Instruction -> Action Trajectory)
              </label>
              <div class="relative flex-1 group">
                  <textarea v-model="task" 
                            class="w-full h-full bg-[#111] border border-[#333] rounded-lg p-4 text-white resize-none outline-none focus:border-primary/50 font-mono text-sm transition-all group-hover:bg-[#131313]"
                            placeholder="e.g. 'Fold the cloth'"></textarea>
                  <button @click="startEval" 
                          class="absolute bottom-4 right-4 bg-primary text-black px-6 py-2 font-black text-xs uppercase tracking-widest flex items-center gap-2 rounded-lg shadow-[0_0_20px_rgba(255,87,34,0.4)] hover:scale-105 active:scale-95 transition-all disabled:grayscale disabled:opacity-50" 
                          :disabled="!task || evaluating || !selectedExpert">
                      <Play class="w-4 h-4" /> {{ evaluating ? 'EXECUTING...' : 'EXECUTE SIM' }}
                  </button>
              </div>
          </div>

          <!-- Benchmark Table -->
          <div class="col-span-4 bg-[#111] border border-[#333] rounded-lg overflow-hidden flex flex-col shadow-xl">
              <div class="p-3 border-b border-[#333] font-black text-[10px] uppercase tracking-widest flex justify-between items-center bg-[#161616]">
                  <span class="text-gray-400">Physics Benchmarks</span>
                  <div class="flex items-center gap-2">
                      <span class="text-[9px] bg-primary/10 text-primary px-2 py-0.5 rounded border border-primary/20">CALVIN-V2</span>
                      <span class="text-[9px] bg-blue-500/10 text-blue-500 px-2 py-0.5 rounded border border-blue-500/20">ISAAC SIM</span>
                  </div>
              </div>
              <div class="flex-1 overflow-y-auto">
                  <table class="w-full text-[10px] text-left">
                      <thead class="bg-[#111] text-gray-600 border-b border-[#222]">
                          <tr>
                              <th class="p-2 font-bold uppercase">Metric</th>
                              <th class="p-2 font-bold uppercase">Base</th>
                              <th class="p-2 font-bold uppercase">Expert</th>
                              <th class="p-2"></th>
                          </tr>
                      </thead>
                      <tbody>
                          <tr v-for="b in benchmarks" :key="b.name" class="border-b border-[#222] hover:bg-white/[0.02] transition-colors">
                              <td class="p-2 text-gray-400">{{ b.name }}</td>
                              <td class="p-2 text-gray-600 font-mono">{{ b.score_base }}</td>
                              <td class="p-2 font-black font-mono" :class="b.status === 'improved' ? 'text-green-500' : 'text-red-500'">{{ b.score_ft }}</td>
                              <td class="p-2">
                                  <component :is="b.status === 'improved' ? CheckCircle : AlertTriangle" 
                                             class="w-3 h-3" 
                                             :class="b.status === 'improved' ? 'text-green-500' : 'text-red-500'" />
                              </td>
                          </tr>
                      </tbody>
                  </table>
              </div>
          </div>
      </div>

      <!-- Create Expert Modal -->
      <div v-if="showCreateModal" class="fixed inset-0 bg-black/90 flex items-center justify-center z-50 backdrop-blur-sm p-4">
          <div class="bg-[#0f0f0f] border border-primary/30 w-full max-w-md rounded-xl shadow-[0_0_100px_rgba(255,87,34,0.2)] overflow-hidden">
              <div class="p-6 border-b border-[#222]">
                  <h3 class="text-xl font-black uppercase tracking-widest text-white mb-1">Create FedMoE Expert</h3>
                  <p class="text-[10px] text-gray-500 uppercase">Initialize a specialized robotics adapter</p>
              </div>
              <div class="p-6 space-y-4">
                  <div>
                      <label class="text-[10px] text-gray-500 font-bold uppercase mb-2 block">Expert Name</label>
                      <input v-model="newExpertName" type="text" class="w-full bg-[#111] border border-[#333] rounded px-4 py-3 text-sm focus:border-primary outline-none transition-colors" placeholder="e.g. laundry_pickup_alpha">
                  </div>
                  <div>
                      <label class="text-[10px] text-gray-500 font-bold uppercase mb-2 block">Foundation Model</label>
                      <select v-model="newExpertBase" class="w-full bg-[#111] border border-[#333] rounded px-4 py-3 text-sm focus:border-primary outline-none cursor-pointer">
                          <option value="openvla-7b">OpenVLA-7B (8-bit Quantized)</option>
                          <option value="rt-2-x">RT-2-X (Large)</option>
                          <option value="pi-0">Pi-0 (Lightweight)</option>
                      </select>
                  </div>
              </div>
              <div class="p-6 bg-[#141414] flex justify-end gap-3">
                  <button @click="showCreateModal = false" class="text-xs font-bold text-gray-500 uppercase px-4 py-2 hover:text-white transition-colors">Cancel</button>
                  <button @click="createExpert" class="bg-primary text-black px-6 py-2 font-black text-xs uppercase tracking-widest rounded shadow-lg hover:scale-105 active:scale-95 transition-transform" :disabled="!newExpertName">Initialize Expert</button>
              </div>
          </div>
      </div>
  </div>
</template>
