<script setup>
import { ref } from 'vue'
import { usePeftStore } from '../stores/peft'
import { Zap, Play, RotateCcw, CheckCircle, FileJson } from 'lucide-vue-next'

const store = usePeftStore()
const steps = [
    'Compute Backend', 
    'VLA Model', 
    'Teleop Dataset', 
    'LoRA Config', 
    'Integrations', 
    'Governance', 
    'Launch'
]
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-2">
        <h2 class="text-2xl font-bold">VLA Adaptation Studio</h2>
        <span class="bg-primary/20 text-primary text-xs px-2 py-0.5 rounded border border-primary/40 font-bold">ROBOTICS ED.</span>
      </div>
      <div class="flex gap-2">
          <button @click="store.applyProfile('local-hf')" class="btn btn-secondary">
            <FileJson class="w-4 h-4 mr-2" />
            Load Profile
          </button>
      </div>
    </div>

    <!-- 2-Column Layout -->
    <div class="flex-1 grid grid-cols-12 gap-6 min-h-0">
      
      <!-- Left: Stepper -->
      <div class="col-span-3 bg-[#0d1117] border border-[#30363d] rounded-lg p-4 overflow-y-auto">
        <div class="space-y-1">
          <div v-for="(label, idx) in steps" :key="idx"
               @click="store.step = idx + 1"
               class="flex items-center gap-3 p-2 rounded cursor-pointer transition-colors"
               :class="store.step === idx + 1 ? 'bg-[#1f2428] text-white' : 'text-gray-500 hover:text-gray-300'"
          >
            <div class="w-6 h-6 rounded flex items-center justify-center text-xs border"
                 :class="store.step > idx + 1 ? 'bg-green-500 border-green-500 text-white' : (store.step === idx + 1 ? 'bg-white text-black border-white' : 'border-gray-600')">
               <span v-if="store.step > idx + 1"><CheckCircle class="w-3 h-3"/></span>
               <span v-else>{{ idx + 1 }}</span>
            </div>
            <span class="font-mono text-sm">{{ label }}</span>
          </div>
        </div>
      </div>

      <!-- Right: Content -->
      <div class="col-span-9 bg-[#0d1117] border border-[#30363d] rounded-lg p-6 overflow-y-auto relative">
        
        <!-- Step 1: Backend -->
        <div v-if="store.step === 1" class="space-y-4">
          <h3 class="text-lg font-bold border-b border-[#333] pb-2">Choose Robotics Simulation Backend</h3>
          <div class="grid grid-cols-2 gap-4">
            <div class="p-4 border rounded cursor-pointer transition-all relative overflow-hidden group"
                 :class="store.config.backend === 'isaac' ? 'border-primary bg-primary/10' : 'border-[#333] hover:border-gray-500'"
                 @click="store.config.backend = 'isaac'">
               <div class="flex justify-between items-start mb-2">
                   <div class="font-bold">NVIDIA Isaac Sim</div>
                   <span class="text-[10px] bg-[#333] px-2 py-0.5 rounded font-mono text-gray-300">CONNECTED</span>
               </div>
               <div class="text-xs text-gray-400">High-fidelity photorealistic rendering for domain randomization.</div>
            </div>
            <div class="p-4 border rounded cursor-pointer transition-all relative overflow-hidden group"
                 :class="store.config.backend === 'mujoco' ? 'border-primary bg-primary/10' : 'border-[#333] hover:border-gray-500'"
                 @click="store.config.backend = 'mujoco'">
               <div class="flex justify-between items-start mb-2">
                   <div class="font-bold">MuJoCo (DeepMind)</div>
                   <span class="text-[10px] bg-red-900/30 text-red-400 px-2 py-0.5 rounded font-mono border border-red-900/50">MISSING</span>
               </div>
               <div class="text-xs text-gray-400">Fast physics engine for contact-rich manipulation tasks.</div>
            </div>
          </div>
          <div class="mt-6">
              <label class="block text-xs text-gray-500 mb-2 uppercase font-bold">Method</label>
              <select class="w-full bg-black border border-[#333] p-2 rounded text-sm text-gray-300 focus:border-primary outline-none">
                  <option>LoRA (Ranked Adaptation)</option>
                  <option>QLoRA (Quantized)</option>
              </select>
          </div>
        </div>

        <!-- Step 4: Hyperparams -->
        <div v-else-if="store.step === 4" class="space-y-6">
            <h3 class="text-lg font-bold border-b border-[#333] pb-2">Hyperparameters</h3>
            <div class="grid grid-cols-2 gap-6">
                <div>
                    <label class="block text-xs text-gray-500 mb-1">Learning Rate</label>
                    <input type="text" value="0.00005" class="w-full bg-black border border-[#333] p-2 rounded text-sm font-mono focus:border-primary outline-none text-white">
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">Batch Size</label>
                    <input type="number" value="4" class="w-full bg-black border border-[#333] p-2 rounded text-sm font-mono focus:border-primary outline-none text-white">
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">Max Steps</label>
                    <input type="number" value="100" class="w-full bg-black border border-[#333] p-2 rounded text-sm font-mono focus:border-primary outline-none text-white">
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">Seed</label>
                    <input type="number" value="42" class="w-full bg-black border border-[#333] p-2 rounded text-sm font-mono focus:border-primary outline-none text-white">
                </div>
            </div>
        </div>

        <!-- Step 5: Integrations -->
        <div v-else-if="store.step === 5" class="space-y-6">
            <h3 class="text-lg font-bold border-b border-[#333] pb-2">Integrations</h3>
            <div class="space-y-4">
                <div class="flex items-center justify-between p-4 border border-[#333] rounded bg-[#111]">
                    <div>
                        <div class="font-bold">MLFlow</div>
                        <div class="text-xs text-gray-500">Log metrics and artifacts</div>
                    </div>
                    <div class="w-10 h-5 bg-[#333] rounded-full relative cursor-pointer">
                        <div class="w-5 h-5 bg-gray-500 rounded-full shadow-md transform scale-110"></div>
                    </div>
                </div>
                <div class="flex items-center justify-between p-4 border border-[#333] rounded bg-[#111]">
                    <div>
                        <div class="font-bold">W&B</div>
                        <div class="text-xs text-gray-500">Experiment tracking</div>
                    </div>
                    <div class="w-10 h-5 bg-[#333] rounded-full relative cursor-pointer">
                        <div class="w-5 h-5 bg-gray-500 rounded-full shadow-md transform scale-110"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Step 6: Review -->
        <div v-else-if="store.step === 6" class="space-y-6">
             <h3 class="text-lg font-bold border-b border-[#333] pb-2">Governance</h3>
             <div class="p-4 border border-[#333] rounded bg-[#111] flex items-center gap-4">
                 <div class="w-5 h-5 border border-primary bg-primary flex items-center justify-center">
                     <CheckCircle class="w-4 h-4 text-black" />
                 </div>
                 <div>
                     <div class="font-bold text-white">Differential Privacy</div>
                     <div class="text-xs text-gray-500">Add DP-SGD noise to gradients (Epsilon=3.0)</div>
                 </div>
             </div>
        </div>


        <!-- Step 2-3: Placeholders (Still simple for now) -->
        <div v-else-if="store.step < 7" class="flex flex-col items-center justify-center h-full text-gray-500">
           <Zap class="w-12 h-12 mb-4 opacity-20" />
           <p>Configuration for {{ steps[store.step - 1] }}</p>
           <button class="mt-4 btn btn-primary" @click="store.step++">Next</button>
        </div>

        <!-- Step 7: Launch -->
        <div v-else class="space-y-6">
           <h3 class="text-lg font-bold border-b border-[#333] pb-2">Launch Training Run</h3>
           
           <div class="bg-[#111] p-4 rounded font-mono text-sm text-gray-400 border border-[#333]">
              <div class="flex justify-between border-b border-[#333] pb-1 mb-1">
                 <span>Backend:</span> <span class="text-primary">{{ store.config.backend }}</span>
              </div>
              <div class="flex justify-between border-b border-[#333] pb-1 mb-1">
                 <span>Learning Rate:</span> <span class="text-white">5e-5</span>
              </div>
              <div class="flex justify-between">
                 <span>Privacy:</span> <span class="text-green-500">DP-SGD Enabled</span>
              </div>
           </div>

           <div v-if="store.run.status === 'idle'">
              <button @click="store.startRun" class="btn btn-primary w-full py-3 flex items-center justify-center gap-2">
                 <Play class="w-4 h-4 text-black font-bold" /> <span class="font-bold text-black">START RUN</span>
              </button>
           </div>
           
           <div v-else class="space-y-4">
              <div class="w-full bg-[#111] rounded-full h-1 border border-[#333]">
                <div class="bg-primary h-full rounded-full transition-all duration-200" :style="{ width: store.run.progress + '%' }"></div>
              </div>
              <div class="bg-black p-4 rounded h-48 overflow-y-auto font-mono text-xs text-primary border border-[#333]">
                 <div v-for="(log, i) in store.run.logs" :key="i">{{ log }}</div>
              </div>
              <button v-if="store.run.status === 'completed'" @click="store.step = 1; store.run.status='idle'" class="btn btn-secondary w-full">
                 <RotateCcw class="w-4 h-4 mr-2 inline" /> Start New Run
              </button>
           </div>
        </div>

      </div>
    </div>
  </div>
</template>

<style scoped>
.btn {
  @apply px-4 py-2 rounded font-medium transition-colors duration-200 flex items-center;
}
.btn-primary {
  @apply bg-orange-600 text-white hover:bg-orange-700;
}
.btn-secondary {
  @apply border border-[#30363d] text-gray-300 hover:text-white hover:bg-[#161b22];
}
</style>
