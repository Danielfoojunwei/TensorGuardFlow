<script setup>
import { ref } from 'vue'
import { Play, AlertTriangle, CheckCircle, Zap, Crosshair, Box } from 'lucide-vue-next'

const task = ref('Pick up the red cube and place it on the blue coaster')
const generated = ref(false)
const evaluating = ref(false)

const startEval = () => {
    if (!task.value) return
    evaluating.value = true
    generated.value = false
    
    // Simulate generation delay
    setTimeout(() => {
        evaluating.value = false
        generated.value = true
    }, 2500)
}

const benchmarks = ref([
    { name: 'Sim Success Rate (SR)', score_base: '42%', score_ft: '89%', status: 'improved' },
    { name: 'Collision Rate', score_base: '15%', score_ft: '0.2%', status: 'improved' },
    { name: 'Command Latency (Hz)', score_base: '5Hz', score_ft: '25Hz', status: 'improved' },
    { name: 'Gripper Slip', score_base: '12mm', score_ft: '14mm', status: 'regressed' },
])
</script>

<template>
  <div class="h-full flex flex-col p-6 space-y-6">
      <!-- Header -->
      <div class="flex items-center justify-between">
          <div>
              <h2 class="text-2xl font-bold">VLA Action Eval Arena</h2>
              <span class="text-xs text-gray-500">Comparing Base vs LoRA-Adapted Policies (OpenVLA-7B)</span>
          </div>
          <div class="flex items-center gap-4">
               <div class="bg-[#111] border border-[#333] px-4 py-2 rounded flex items-center gap-2 opacity-50">
                   <span class="text-xs text-gray-500 uppercase">Baseline</span>
                   <span class="font-bold text-white">RT-2-X (Zero-shot)</span>
               </div>
               <span class="text-gray-500">VS</span>
               <div class="bg-[#111] border border-[#333] px-4 py-2 rounded flex items-center gap-2 border-primary">
                   <span class="text-xs text-gray-500 uppercase">Adapted Policy</span>
                   <span class="font-bold text-primary">v2.1-teleop-lora</span>
               </div>
          </div>
      </div>

      <!-- Main Compare View -->
      <div class="flex-1 grid grid-cols-2 gap-6 min-h-0">
          
          <!-- Base Policy Visualization -->
          <div class="bg-[#111] border border-[#333] rounded-lg flex flex-col overflow-hidden relative grayscale opacity-60">
             <div class="p-3 border-b border-[#333] bg-[#161616] flex justify-between">
                 <span class="font-bold text-sm text-gray-400">Baseline Trajectory</span>
                 <span class="text-xs text-red-500 font-bold">FAILURE</span>
             </div>
             
             <!-- Mock Sim View -->
             <div class="flex-1 relative bg-[#050505] overflow-hidden flex items-center justify-center p-8">
                 <div class="absolute inset-0 grid grid-cols-12 grid-rows-12 gap-1 opacity-10 pointer-events-none">
                     <div v-for="i in 144" :key="i" class="border border-green-500/20"></div>
                 </div>
                 <!-- Sim Elements -->
                 <div class="relative w-full h-full border border-[#333] rounded p-4 flex items-center justify-center">
                      <div class="w-16 h-16 border-2 border-gray-600 rounded flex items-center justify-center text-xs text-gray-600">Blue Pad</div>
                      <div class="absolute top-10 left-10 w-8 h-8 bg-red-800 rounded flex items-center justify-center text-[8px] text-white">Cube</div>
                      <!-- Failed Path -->
                      <svg class="absolute inset-0 w-full h-full pointer-events-none">
                          <path d="M 50 50 Q 100 150 200 100" stroke="#333" stroke-width="2" fill="none" stroke-dasharray="5,5" />
                          <circle cx="200" cy="100" r="4" fill="red" />
                      </svg>
                 </div>
             </div>
          </div>

          <!-- Fine-Tuned Policy Visualization -->
          <div class="bg-[#111] border border-[#333] rounded-lg flex flex-col overflow-hidden relative" :class="generated ? 'border-primary' : ''">
             <div class="p-3 border-b border-[#333] bg-[#161616] flex justify-between">
                 <span class="font-bold text-sm text-primary">LoRA Policy Trajectory</span>
                 <span v-if="generated" class="text-xs text-green-500 font-bold animate-pulse">SUCCESS (0.8s)</span>
             </div>
             
             <!-- Mock Sim View Active -->
             <div class="flex-1 relative bg-[#050505] overflow-hidden flex items-center justify-center p-8">
                 <div class="absolute inset-0 grid grid-cols-12 grid-rows-12 gap-1 opacity-20 pointer-events-none">
                     <div v-for="i in 144" :key="i" class="border border-green-500/20"></div>
                 </div>
                 
                 <div v-if="!generated && !evaluating" class="absolute inset-0 flex items-center justify-center text-gray-600 font-mono">
                     Ready for Simulation Task
                 </div>

                 <div v-if="evaluating" class="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black/50 z-10 backdrop-blur-sm">
                     <div class="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
                     <div class="font-mono text-primary text-xs tracking-widest uppercase">Running Physics Sim...</div>
                 </div>

                 <!-- Success Visual -->
                 <div v-if="generated" class="relative w-full h-full border border-primary/30 rounded p-4 flex items-center justify-center">
                      <div class="w-16 h-16 border-2 border-blue-500 rounded flex items-center justify-center text-xs text-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.5)]">
                           <div class="w-8 h-8 bg-red-600 rounded flex items-center justify-center text-[8px] text-white shadow-lg">Cube</div>
                      </div>
                      <!-- Trajectory -->
                      <svg class="absolute inset-0 w-full h-full pointer-events-none">
                          <path d="M 50 50 Q 150 50 250 150 T 400 200" stroke="#ff5722" stroke-width="3" fill="none" class="drop-shadow-[0_0_5px_rgba(255,87,34,0.8)]" />
                          <circle cx="400" cy="200" r="4" fill="#ff5722" />
                      </svg>
                 </div>
             </div>
             
             <!-- Action Histogram overlay -->
             <div v-if="generated" class="absolute bottom-4 right-4 bg-black/90 border border-[#333] p-3 rounded backdrop-blur-md text-xs w-48">
                 <div class="text-gray-500 mb-2 font-bold uppercase text-[10px]">Action Distribution (XYZ)</div>
                 <div class="flex gap-1 h-8 items-end">
                     <div class="w-2 bg-red-500 h-full rounded-t-sm"></div>
                     <div class="w-2 bg-green-500 h-3/4 rounded-t-sm"></div>
                     <div class="w-2 bg-blue-500 h-1/2 rounded-t-sm"></div>
                     <div class="w-2 bg-red-500 h-2/3 rounded-t-sm"></div>
                     <div class="w-2 bg-green-500 h-1/4 rounded-t-sm"></div>
                     <div class="w-2 bg-blue-500 h-full rounded-t-sm"></div>
                     <div class="w-2 bg-red-500 h-1/2 rounded-t-sm"></div>
                 </div>
             </div>
          </div>
      </div>

      <!-- Input Area & Benchmarks -->
      <div class="h-1/3 grid grid-cols-12 gap-6">
          <!-- Input -->
          <div class="col-span-8 flex flex-col">
              <label class="text-xs text-gray-500 font-bold mb-2 uppercase">Natural Language Instruction (VLA Input)</label>
              <div class="relative flex-1">
                  <textarea v-model="task" 
                            class="w-full h-full bg-[#111] border border-[#333] rounded p-4 text-white resize-none outline-none focus:border-primary font-mono text-sm"
                            placeholder="e.g. 'Fold the cloth'"></textarea>
                  <button @click="startEval" class="absolute bottom-4 right-4 btn btn-primary px-6 py-2 font-bold flex items-center gap-2 rounded shadow-lg hover:scale-105 transition-transform" :disabled="!task || evaluating">
                      <Play class="w-4 h-4" /> {{ evaluating ? 'SIMULATING...' : 'EXECUTE SIM' }}
                  </button>
              </div>
          </div>

          <!-- Benchmark Table -->
          <div class="col-span-4 bg-[#111] border border-[#333] rounded-lg overflow-hidden flex flex-col">
              <div class="p-3 border-b border-[#333] font-bold text-sm flex justify-between items-center">
                  <span>Robotics Benchmarks</span>
                  <span class="text-[10px] bg-primary/20 text-primary px-2 py-0.5 rounded border border-primary/30">Calvin-v2</span>
              </div>
              <div class="flex-1 overflow-y-auto">
                  <table class="w-full text-xs text-left">
                      <thead class="bg-[#161616] text-gray-500">
                          <tr>
                              <th class="p-2">Metric</th>
                              <th class="p-2">Base</th>
                              <th class="p-2">LoRA</th>
                              <th class="p-2"></th>
                          </tr>
                      </thead>
                      <tbody>
                          <tr v-for="b in benchmarks" :key="b.name" class="border-b border-[#333]">
                              <td class="p-2 font-medium">{{ b.name }}</td>
                              <td class="p-2 text-gray-400 font-mono">{{ b.score_base }}</td>
                              <td class="p-2 font-bold font-mono" :class="b.status === 'improved' ? 'text-green-500' : 'text-red-500'">{{ b.score_ft }}</td>
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
  </div>
</template>
