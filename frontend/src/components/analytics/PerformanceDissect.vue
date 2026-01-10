<script setup>
import { Activity, Lock, AlertTriangle } from 'lucide-vue-next'

// Mock Data for Flame Graph
const trace = [
  { stage: 'Edge Compute (Fwd/Bwd)', duration: 120, start: 0, color: 'bg-blue-500' },
  { stage: 'N2HE Encryption', duration: 45, start: 120, color: 'bg-purple-500' },
  { stage: 'Network Transmit', duration: 80, start: 165, color: 'bg-primary' }, // Orange = Lag?
  { stage: 'Cloud Aggregation', duration: 60, start: 245, color: 'bg-green-500' },
]

// Mock Data for Trade-offs
const tradeoffs = [
  { eps: 0.1, acc: 0.82 },
  { eps: 0.5, acc: 0.88 },
  { eps: 1.0, acc: 0.92 }, // Current
  { eps: 5.0, acc: 0.94 },
  { eps: 10.0, acc: 0.95 },
]
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
       <div>
         <h2 class="text-2xl font-bold">Mission Control: Observability</h2>
         <span class="text-xs text-gray-500">Timing Loops, Security Trade-offs, and Key Lifecycle</span>
       </div>
    </div>

    <!-- Top Row: Flame Graph -->
    <div class="bg-[#111] border border-[#333] p-6 rounded-lg">
       <div class="flex items-center justify-between mb-6">
          <h3 class="font-bold flex items-center gap-2">
             <Activity class="w-4 h-4 text-primary" /> Real-Time Execution Trace
          </h3>
          <span class="text-xs font-mono text-gray-500">Round #4092 • Total: 305ms</span>
       </div>
       
       <!-- Timeline Container -->
       <div class="relative h-16 w-full bg-black rounded border border-[#333] overflow-hidden flex">
          <div v-for="(seg, i) in trace" :key="i" 
               class="h-full flex items-center justify-center text-[10px] font-bold text-white/90 border-r border-black/20 hover:opacity-90 cursor-pointer transition-all"
               :class="seg.color"
               :style="{ width: (seg.duration / 305 * 100) + '%' }">
             {{ seg.stage }} ({{ seg.duration }}ms)
          </div>
       </div>
       <div class="flex justify-between text-xs font-mono text-gray-600 mt-2">
          <span>0ms</span>
          <span>150ms</span>
          <span>300ms</span>
       </div>
    </div>

    <!-- Bottom Row: Trade-off Matrix & Key Timeline -->
    <div class="grid grid-cols-2 gap-6">
       
       <!-- Trade-off Matrix -->
       <div class="bg-[#111] border border-[#333] p-6 rounded-lg">
          <div class="flex items-center justify-between mb-4">
             <h3 class="font-bold flex items-center gap-2">
                <Lock class="w-4 h-4 text-primary" /> Privacy-Utility Frontier
             </h3>
          </div>
          
          <div class="h-64 relative border-l border-b border-[#333] bg-black/50 p-4">
             <!-- Scatter Points -->
             <div v-for="(pt, i) in tradeoffs" :key="i" 
                  class="absolute w-3 h-3 rounded-full border-2 border-primary bg-black hover:bg-primary transition-colors cursor-pointer"
                  :style="{ left: (pt.eps / 10 * 100) + '%', bottom: ((pt.acc - 0.8) / 0.2 * 100) + '%' }"
                  :title="`Epsilon: ${pt.eps}, Acc: ${pt.acc}`">
             </div>
             
             <!-- Trend Line (Visual Only) -->
             <svg class="absolute inset-0 pointer-events-none" preserveAspectRatio="none">
                <path d="M 10 200 Q 150 50 300 20" fill="none" stroke="#333" stroke-width="2" stroke-dasharray="4"/>
             </svg>
             
             <!-- Labels -->
             <div class="absolute bottom-2 right-2 text-xs text-gray-500">Privacy Budget (ε) →</div>
             <div class="absolute top-2 left-2 text-xs text-gray-500">Model Accuracy ↑</div>
          </div>
       </div>

       <!-- Key Rotation Timeline -->
        <div class="bg-[#111] border border-[#333] p-6 rounded-lg">
          <div class="flex items-center justify-between mb-4">
             <h3 class="font-bold flex items-center gap-2">
                <AlertTriangle class="w-4 h-4 text-primary" /> Key Rotation Gantt
             </h3>
          </div>
          
          <div class="space-y-4 font-mono text-xs">
             <!-- Row 1 -->
             <div>
                <div class="flex justify-between mb-1 text-gray-400">
                   <span>Master Key (KMS-ROOT)</span>
                   <span>30d Policy</span>
                </div>
                <div class="h-4 w-full bg-black rounded overflow-hidden flex">
                   <div class="w-3/4 bg-gray-700"></div> <!-- Expired -->
                   <div class="w-1/4 bg-primary animate-pulse"></div> <!-- Active -->
                </div>
             </div>
             
             <!-- Row 2 -->
             <div>
                <div class="flex justify-between mb-1 text-gray-400">
                   <span>Fleet-US-East (KMS-FLEET)</span>
                   <span>24h Policy</span>
                </div>
                <div class="h-4 w-full bg-black rounded overflow-hidden flex gap-1">
                   <div class="w-1/6 bg-gray-700"></div>
                   <div class="w-1/6 bg-gray-700"></div>
                   <div class="w-1/6 bg-gray-700"></div>
                   <div class="w-1/6 bg-gray-700"></div>
                   <div class="w-1/6 bg-gray-700"></div>
                   <div class="w-1/6 bg-primary"></div>
                </div>
             </div>
          </div>
       </div>

    </div>
  </div>
</template>
