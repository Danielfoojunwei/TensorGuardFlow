<script setup>
import { ref, onMounted } from 'vue'
import { VueFlow, useVueFlow, Handle, Position } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { Play, Server, Cloud, Cpu, Plus, Rocket, Activity, AlertTriangle, Link as LinkIcon, Trash2 } from 'lucide-vue-next'
import NodeInspector from '../modals/NodeInspector.vue'
import LinkInspector from '../modals/LinkInspector.vue'

// Initial Nodes
const initialNodes = [
  { 
    id: 'edge-1', 
    type: 'custom', 
    label: 'UR5e (Pick & Place)', 
    position: { x: 100, y: 150 }, 
    data: { role: 'edge', status: 'online', gpu: 'Orin NX', metrics: { loss: 0.04 }, version: 'v2.1' } 
  },
  { 
    id: 'edge-2', 
    type: 'custom', 
    label: 'Franka Emika (Assembly)', 
    position: { x: 100, y: 350 }, 
    data: { role: 'edge', status: 'training', gpu: 'AGX Orin', metrics: { loss: 0.12 }, drift: 'Severe Oscillation' } 
  },
  { 
    id: 'agg-1', 
    type: 'custom', 
    label: 'Fleet Aggregator (FedAvg)', 
    position: { x: 500, y: 250 }, 
    data: { role: 'aggregator', status: 'idle', region: 'us-east-1', version: 'v2.1' } 
  },
  { 
    id: 'cloud-1', 
    type: 'custom', 
    label: 'Global Model Registry', 
    position: { x: 900, y: 250 }, 
    data: { role: 'cloud', status: 'active', version: 'v2.1' } 
  },
]

// Connections
const initialEdges = [
  { id: 'e1-agg', source: 'edge-1', target: 'agg-1', animated: true, style: { stroke: '#ff5722' } },
]

const nodes = ref(initialNodes)
const edges = ref(initialEdges)

const { onNodeClick, onEdgeClick: onVueFlowEdgeClick, addEdges, fitView, addNodes } = useVueFlow()
const selectedNode = ref(null)
const selectedEdge = ref(null)
const deploying = ref(false)

// Center graph on load
onMounted(() => {
    setTimeout(() => {
        fitView({ padding: 0.2 })
    }, 100)
})

const onConnect = (params) => {
    addEdges([params])
}

const triggerTraining = (nodeId) => {
  const node = nodes.value.find(n => n.id === nodeId)
  if (node) {
     node.data.status = 'training'
     setTimeout(() => { node.data.status = 'online' }, 3000)
  }
}

const addRandomNode = () => {
    const id = `edge-${Math.floor(Math.random() * 1000)}`
    const newNode = {
        id,
        type: 'custom',
        label: 'New Robot Node',
        position: { x: 100, y: Math.random() * 400 },
        data: { role: 'edge', status: 'idle', gpu: 'Jetson Nano', metrics: { loss: 0.00 } }
    }
    addNodes([newNode])
}

const deployFleet = async () => {
    deploying.value = true
    setTimeout(() => {
        deploying.value = false
        alert("Deployment initialized: Update package sent to 4 active nodes.")
    }, 1500)
}
</script>

<template>
  <div class="h-full w-full relative bg-[#000000] text-white">
    <!-- Cloud/Edge Swimlanes -->
    <div class="absolute inset-0 pointer-events-none flex">
       <div class="w-1/2 border-r border-[#333] h-full relative">
           <div class="absolute top-4 left-4 font-bold text-[#333] text-4xl uppercase select-none opacity-20">Edge Fleet</div>
       </div>
       <div class="w-1/2 h-full relative">
           <div class="absolute top-4 right-4 font-bold text-[#333] text-4xl uppercase select-none opacity-20 text-right">Cloud Aggregation</div>
       </div>
    </div>

    <!-- Vue Flow Canvas -->
    <VueFlow v-model="nodes" 
             :edges="edges" 
             class="h-full w-full" 
             :min-zoom="0.5" 
             :max-zoom="2"
             @connect="onConnect"
             @node-click="(e) => selectedNode = e.node"
             @edge-click="(e) => selectedEdge = e.edge">
       
       <Background pattern-color="#333" :gap="20" />
       <Controls class="bg-[#111] border border-[#333] !fill-white" />
       
       <!-- Custom Node Template -->
       <template #node-custom="{ data, label, id }">
          <div class="w-64 bg-[#111] border rounded-lg shadow-xl transition-all duration-200 group relative"
               :class="data.status === 'training' ? 'border-primary ring-1 ring-primary' : 'border-[#333] hover:border-gray-500'">
             
             <!-- Handles for Connectivity -->
             <Handle v-if="data.role !== 'edge'" type="target" :position="Position.Left" class="!bg-primary !w-3 !h-3 !border-2 !border-black" />
             <Handle v-if="data.role !== 'cloud'" type="source" :position="Position.Right" class="!bg-primary !w-3 !h-3 !border-2 !border-black" />

             <!-- Header -->
             <div class="px-4 py-2 border-b border-[#333] bg-[#161616] rounded-t-lg flex items-center justify-between">
                <div class="flex items-center gap-2">
                   <component :is="data.role === 'edge' ? Cpu : (data.role === 'aggregator' ? Server : Cloud)" 
                              class="w-4 h-4 text-primary" />
                   <span class="font-bold font-sans text-sm">{{ label }}</span>
                </div>
                <!-- Action Button -->
                <button v-if="data.role === 'edge'" @click.stop="triggerTraining(id)" 
                        class="p-1 rounded hover:bg-[#333] transition-colors" title="Execute Training">
                   <Play class="w-3 h-3 text-white" :class="data.status === 'training' ? 'fill-primary text-primary' : ''" />
                </button>
             </div>

             <!-- Body -->
             <div class="p-4 space-y-2">
                <div class="flex justify-between items-center text-xs">
                   <span class="text-gray-500 uppercase">Status</span>
                   <span class="font-mono" :class="data.status === 'training' ? 'text-primary animate-pulse' : 'text-green-500'">
                      {{ data.status.toUpperCase() }}
                   </span>
                </div>
                
                <div v-if="data.role === 'edge'" class="flex justify-between items-center text-xs">
                   <span class="text-gray-500 uppercase">Hardware</span>
                   <span class="font-mono text-gray-300">{{ data.gpu }}</span>
                </div>
                
                <!-- Behavioral Drift Alert (VLA Specific) -->
                <div v-if="data.drift" class="mt-2 bg-red-900/20 border border-red-900 rounded p-1 text-center animate-pulse">
                    <div class="text-[10px] text-red-500 font-bold uppercase flex items-center justify-center gap-1">
                        <AlertTriangle class="w-3 h-3" /> {{ data.drift }}
                    </div>
                </div>

                <div v-if="data.metrics" class="mt-2 pt-2 border-t border-[#333]">
                   <div class="flex justify-between items-center text-xs">
                      <span class="text-gray-500">Current Loss</span>
                      <span class="font-mono text-primary">{{ data.metrics.loss }}</span>
                   </div>
                   <!-- Mini Sparkline Simulation -->
                   <div class="h-1 w-full bg-[#333] mt-1 rounded overflow-hidden">
                      <div class="h-full bg-primary/50" style="width: 65%"></div>
                   </div>
                </div>
             </div>
          </div>
       </template>

    </VueFlow>

    <!-- Global Operations Toolbar -->
    <div class="absolute bottom-8 left-1/2 transform -translate-x-1/2 bg-[#111] border border-[#333] rounded-full px-6 py-3 flex items-center gap-6 shadow-2xl z-20">
        <button @click="addRandomNode" class="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm font-bold">
            <Plus class="w-4 h-4" /> ADD NODE
        </button>
        <div class="w-[1px] h-4 bg-[#333]"></div>
        <button class="flex items-center gap-2 text-gray-400 hover:text-white transition-colors text-sm font-bold">
            <Activity class="w-4 h-4" /> AUTO-SCALE
        </button>
        <div class="w-[1px] h-4 bg-[#333]"></div>
        <button @click="deployFleet" class="flex items-center gap-2 transition-colors text-sm font-bold" 
                :class="deploying ? 'text-yellow-500' : 'text-primary hover:text-orange-300'">
            <Rocket class="w-4 h-4" :class="deploying ? 'animate-bounce' : ''" /> 
            {{ deploying ? 'DEPLOYING...' : 'DEPLOY ALL' }}
        </button>
    </div>

    <!-- Modals -->
    <NodeInspector v-if="selectedNode" :node="selectedNode" @close="selectedNode = null" />
    <LinkInspector v-if="selectedEdge" :edge="selectedEdge" @close="selectedEdge = null" />
  </div>
</template>

<style>
.vue-flow__node-custom {
  @apply select-none;
}
.vue-flow__edge-path {
  stroke-width: 2;
  stroke: #666;
}
.vue-flow__edge.selected .vue-flow__edge-path {
  stroke: #ff5722;
}
</style>
