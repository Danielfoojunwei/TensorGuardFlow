<script setup>
import { ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import Header from './components/Header.vue'
import NodeCanvas from './components/flow/NodeCanvas.vue' // New N8n Canvas
import PerformanceDissect from './components/analytics/PerformanceDissect.vue' // New Metrics
import PeftStudio from './components/PeftStudio.vue'
import ModelLineage from './components/ModelLineage.vue'
import ComplianceRegistry from './components/ComplianceRegistry.vue'
import KeyVault from './components/KeyVault.vue'
import AuditTrail from './components/AuditTrail.vue'
import FleetsDevices from './components/FleetsDevices.vue'
import GlobalSettings from './components/GlobalSettings.vue'

import EvalArena from './components/EvalArena.vue'

const activeTab = ref('canvas') // Default to Canvas
</script>

<template>
  <div class="flex h-screen bg-background text-secondary overflow-hidden">
    <!-- Sidebar -->
    <Sidebar :activeTab="activeTab" @update:activeTab="t => activeTab = t" />

    <!-- Main Content -->
    <div class="flex-1 flex flex-col ml-64 transition-all duration-300">
      <Header />

      <main class="flex-1 overflow-y-auto p-0 relative">
        <!-- Content Switcher -->
        <transition name="fade" mode="out-in">
          <!-- Canvas takes full height/width, no padding -->
          <div v-if="activeTab === 'canvas'" class="h-full w-full">
             <NodeCanvas />
          </div>

          <div v-else-if="activeTab === 'performance'" class="p-6">
             <PerformanceDissect />
          </div>

          <div v-else-if="activeTab === 'eval'" class="h-full w-full">
             <EvalArena />
          </div>

          <div v-else class="p-6">
            <PeftStudio v-if="activeTab === 'peft-studio'" />
            <ModelLineage v-else-if="activeTab === 'lineage'" />
            <ComplianceRegistry v-else-if="activeTab === 'compliance'" />
            <KeyVault v-else-if="activeTab === 'vault'" />
            <AuditTrail v-else-if="activeTab === 'audit'" />
            <FleetsDevices v-else-if="activeTab === 'fleets'" />
            <GlobalSettings v-else-if="activeTab === 'settings'" />
          </div>
        </transition>
      </main>
    </div>
  </div>
</template>


<style>
.bg-app { background-color: #000000; }
.bg-card { background-color: #0d1117; }
.border-border { border-color: #30363d; }

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
