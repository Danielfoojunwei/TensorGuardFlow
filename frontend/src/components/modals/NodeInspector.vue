<script setup>
import { 
  Settings, Activity, X, Globe, HardDrive, 
  Wifi, Sliders, CheckCircle, Plus, TerminalSquare, Cpu
} from 'lucide-vue-next'
import { ref } from 'vue'

const props = defineProps(['node'])
const emit = defineEmits(['close'])

const activeTab = ref('config')

const integrations = ref([
  { id: 'aws', name: 'AWS KMS', connected: true, logo: 'https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg' },
  { id: 'mlflow', name: 'MLflow', connected: false, logo: 'https://upload.wikimedia.org/wikipedia/commons/3/38/Jupyter_logo.svg' }, // Placeholder logo
  { id: 'slack', name: 'Slack Alerts', connected: false, logo: 'https://upload.wikimedia.org/wikipedia/commons/d/d5/Slack_icon_2019.svg' },
])

const connect = (id) => {
    const integration = integrations.value.find(i => i.id === id)
    if (integration) {
        integration.connected = !integration.connected
    }
}
</script>

<template>
<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm" @click.self="$emit('close')">
   <div class="bg-[#111] border border-[#333] rounded-xl shadow-2xl w-[800px] h-[600px] flex overflow-hidden">
      
      <!-- Sidebar -->
      <div class="w-64 bg-black border-r border-[#333] p-4">
         <div class="flex items-center gap-3 mb-8">
             <div class="w-10 h-10 bg-[#222] rounded flex items-center justify-center border border-[#333]">
                 <span class="font-bold text-xl text-primary font-mono">{{ node.label.substring(0,2).toUpperCase() }}</span>
             </div>
             <div>
                 <div class="font-bold">{{ node.label }}</div>
                 <div class="text-xs text-gray-500 font-mono">{{ node.id }}</div>
             </div>
         </div>

         <div class="space-y-1">
             <button @click="activeTab = 'config'" 
                     class="w-full text-left px-3 py-2 rounded text-sm font-medium flex items-center gap-2"
                     :class="activeTab === 'config' ? 'bg-[#222] text-white' : 'text-gray-400 hover:text-white'">
                 <Sliders class="w-4 h-4" /> Configuration
             </button>
             <button @click="activeTab = 'terminal'" 
                     class="w-full text-left px-3 py-2 rounded text-sm font-medium flex items-center gap-2"
                     :class="activeTab === 'terminal' ? 'bg-[#222] text-white' : 'text-gray-400 hover:text-white'">
                 <TerminalSquare class="w-4 h-4" /> Terminal
             </button>
             <button @click="activeTab = 'logs'" 
                     class="w-full text-left px-3 py-2 rounded text-sm font-medium flex items-center gap-2"
                     :class="activeTab === 'logs' ? 'bg-[#222] text-white' : 'text-gray-400 hover:text-white'">
                 <Activity class="w-4 h-4" /> Live Logs
             </button>
             <button @click="activeTab = 'services'" 
                     class="w-full text-left px-3 py-2 rounded text-sm font-medium flex items-center gap-2"
                     :class="activeTab === 'services' ? 'bg-[#222] text-white' : 'text-gray-400 hover:text-white'">
                 <Cpu class="w-4 h-4" /> System Services
             </button>
             <button @click="activeTab = 'integrations'" 
                     class="w-full text-left px-3 py-2 rounded text-sm font-medium flex items-center gap-2"
                     :class="activeTab === 'integrations' ? 'bg-[#222] text-white' : 'text-gray-400 hover:text-white'">
                 <Globe class="w-4 h-4" /> Integrations
             </button>
         </div>
      </div>

      <!-- Content -->
      <div class="flex-1 p-6 overflow-y-auto bg-[#0a0a0a]">
          
          <div v-if="activeTab === 'config'" class="space-y-6">
              <h3 class="text-lg font-bold border-b border-[#333] pb-2 mb-4">Node Configuration</h3>
              
              <div class="grid grid-cols-2 gap-4">
                  <div class="bg-[#111] border border-[#333] p-4 rounded">
                      <div class="text-xs text-gray-500 mb-1">Compute Backend</div>
                      <div class="font-mono text-sm">{{ node.data.gpu || 'Generic CPU' }}</div>
                  </div>
                  <div class="bg-[#111] border border-[#333] p-4 rounded">
                      <div class="text-xs text-gray-500 mb-1">Operational State</div>
                      <div class="font-mono text-sm flex items-center gap-2">
                          <div class="w-2 h-2 rounded-full" :class="node.data.status === 'online' ? 'bg-green-500' : 'bg-orange-500'"></div>
                          {{ node.data.status.toUpperCase() }}
                      </div>
                  </div>
              </div>

              <div>
                  <div class="text-xs text-gray-500 mb-2">Raw JSON definition</div>
                  <textarea class="w-full h-48 bg-[#050505] border border-[#333] rounded p-3 font-mono text-xs text-gray-300 focus:border-primary outline-none resize-none" readonly>{{ JSON.stringify(node.data, null, 2) }}</textarea>
              </div>
          </div>

          <!-- Terminal Tab -->
          <div v-if="activeTab === 'terminal'" class="h-full flex flex-col">
              <h3 class="text-lg font-bold border-b border-[#333] pb-2 mb-4">Secure Shell Access (SSH)</h3>
              <div class="flex-1 bg-black border border-[#333] rounded p-4 font-mono text-xs overflow-hidden flex flex-col">
                  <div class="flex-1 text-gray-300 space-y-1">
                      <div><span class="text-green-500">root@{{ node.id }}:~#</span> uptime</div>
                      <div class="text-gray-500"> 14:24:02 up 42 days,  3:14,  1 user,  load average: 0.04, 0.08, 0.04</div>
                      <div><span class="text-green-500">root@{{ node.id }}:~#</span> nvidia-smi</div>
                      <div class="text-gray-500 whitespace-pre">
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 525.60.13    Driver Version: 525.60.13    CUDA Version: 12.0     |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|                               |                      |               MIG M. |
|===============================+======================+======================|
|   0  NVIDIA A100-SXM...  On   | 00000000:00:04.0 Off |                    0 |
| N/A   32C    P0    44W / 400W |      0MiB / 40960MiB |      0%      Default |
|                               |                      |             Disabled |
+-------------------------------+----------------------+----------------------+
                      </div>
                      <div><span class="text-green-500">root@{{ node.id }}:~#</span> <span class="animate-pulse">_</span></div>
                  </div>
                  <input type="text" class="bg-transparent border-none outline-none text-white w-full mt-2" placeholder="Type command...">
              </div>
          </div>

          <!-- Services Tab -->
          <div v-if="activeTab === 'services'" class="space-y-6">
               <h3 class="text-lg font-bold border-b border-[#333] pb-2 mb-4">Service Control</h3>
               
               <div class="space-y-4">
                   <div v-for="svc in ['docker', 'kubelet', 'tensor-guard-agent']" :key="svc" class="flex items-center justify-between p-4 border border-[#333] rounded bg-[#111]">
                       <div class="flex items-center gap-3">
                           <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                           <span class="font-mono font-bold">{{ svc }}</span>
                           <span class="text-xs text-gray-500">PID: {{ Math.floor(Math.random() * 9999) }}</span>
                       </div>
                       <div class="flex gap-2">
                           <button class="px-2 py-1 bg-[#222] border border-[#333] rounded text-xs hover:bg-white hover:text-black">RESTART</button>
                           <button class="px-2 py-1 bg-[#222] border border-[#333] rounded text-xs hover:bg-red-900 hover:text-red-200 hover:border-red-900">KILL</button>
                       </div>
                   </div>
               </div>
          </div>

          <div v-if="activeTab === 'integrations'" class="space-y-6">
              <h3 class="text-lg font-bold border-b border-[#333] pb-2 mb-4">Integration Hub</h3>
              <p class="text-sm text-gray-400 mb-4">Connect this node to external services for augmented telemetry and security.</p>
              
              <div class="grid grid-cols-2 gap-4">
                  <div v-for="item in integrations" :key="item.id" 
                       class="bg-[#111] border border-[#333] p-4 rounded flex items-center justify-between hover:border-gray-500 transition-colors">
                      <div class="flex items-center gap-3">
                          <div class="w-10 h-10 bg-white rounded p-1 flex items-center justify-center">
                              <img :src="item.logo" :alt="item.name" class="w-full h-full object-contain">
                          </div>
                          <span class="font-bold text-sm">{{ item.name }}</span>
                      </div>
                      
                      <button @click="connect(item.id)" 
                              class="px-3 py-1.5 rounded textxs font-bold transition-all border"
                              :class="item.connected ? 'bg-green-900/20 text-green-400 border-green-900' : 'bg-[#222] text-gray-400 border-[#333] hover:bg-[#333] hover:text-white'">
                          {{ item.connected ? 'Connected' : 'Connect' }}
                      </button>
                  </div>
              </div>
          </div>

      </div>
   </div>
</div>
</template>
