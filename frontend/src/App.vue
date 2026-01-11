<script setup>
import { ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import Header from './components/Header.vue'

// Core
import NodeCanvas from './components/flow/NodeCanvas.vue'
import TrainingMonitor from './components/TrainingMonitor.vue'
import PerformanceDissect from './components/analytics/PerformanceDissect.vue'

// Models & Training
import VLARegistry from './components/VLARegistry.vue'
import PeftStudio from './components/PeftStudio.vue'
import EvalArena from './components/EvalArena.vue'
import SkillsLibrary from './components/SkillsLibrary.vue'

// Security & Identity
import IdentityManager from './components/IdentityManager.vue'
import KeyVault from './components/KeyVault.vue'
import PolicyGating from './components/PolicyGating.vue'
import ForensicsPanel from './components/ForensicsPanel.vue'

// Deployment & Ops
import TGSPMarketplace from './components/TGSPMarketplace.vue'
import IntegrationsHub from './components/IntegrationsHub.vue'
import FleetsDevices from './components/FleetsDevices.vue'
import ModelLineage from './components/ModelLineage.vue'

// Compliance
import ComplianceRegistry from './components/ComplianceRegistry.vue'
import AuditTrail from './components/AuditTrail.vue'
import GlobalSettings from './components/GlobalSettings.vue'

const activeTab = ref('canvas')
</script>

<template>
  <div class="flex h-screen bg-background text-secondary overflow-hidden">
    <!-- Sidebar -->
    <Sidebar :activeTab="activeTab" @update:activeTab="t => activeTab = t" />

    <!-- Main Content -->
    <div class="flex-1 flex flex-col ml-64 transition-all duration-300">
      <Header />

      <main class="flex-1 overflow-hidden relative">
        <!-- Content Switcher -->
        <transition name="fade" mode="out-in">
          <!-- Core Section -->
          <div v-if="activeTab === 'canvas'" class="absolute inset-0">
             <NodeCanvas @navigate="t => activeTab = t" />
          </div>

          <div v-else-if="activeTab === 'monitor'" class="h-full overflow-y-auto p-6">
             <TrainingMonitor />
          </div>

          <div v-else-if="activeTab === 'performance'" class="h-full overflow-y-auto p-6">
             <PerformanceDissect />
          </div>

          <!-- Models & Training Section -->
          <div v-else-if="activeTab === 'vla-registry'" class="h-full overflow-y-auto p-6">
             <VLARegistry />
          </div>

          <div v-else-if="activeTab === 'peft-studio'" class="h-full overflow-y-auto p-6">
             <PeftStudio />
          </div>

          <div v-else-if="activeTab === 'eval'" class="h-full w-full">
             <EvalArena />
          </div>

          <div v-else-if="activeTab === 'skills'" class="h-full overflow-y-auto p-6">
             <SkillsLibrary />
          </div>

          <!-- Security & Identity Section -->
          <div v-else-if="activeTab === 'identity'" class="h-full overflow-y-auto p-6">
             <IdentityManager />
          </div>

          <div v-else-if="activeTab === 'vault'" class="h-full overflow-y-auto p-6">
             <KeyVault />
          </div>

          <div v-else-if="activeTab === 'policy'" class="h-full overflow-y-auto p-6">
             <PolicyGating />
          </div>

          <div v-else-if="activeTab === 'forensics'" class="h-full overflow-y-auto p-6">
             <ForensicsPanel />
          </div>

          <!-- Deployment & Ops Section -->
          <div v-else-if="activeTab === 'tgsp-marketplace'" class="h-full overflow-y-auto p-6">
             <TGSPMarketplace />
          </div>

          <div v-else-if="activeTab === 'integrations'" class="h-full overflow-y-auto p-6">
             <IntegrationsHub />
          </div>

          <div v-else-if="activeTab === 'fleets'" class="h-full overflow-y-auto p-6">
             <FleetsDevices />
          </div>

          <div v-else-if="activeTab === 'lineage'" class="h-full overflow-y-auto p-6">
             <ModelLineage />
          </div>

          <!-- Compliance Section -->
          <div v-else-if="activeTab === 'compliance'" class="h-full overflow-y-auto p-6">
             <ComplianceRegistry />
          </div>

          <div v-else-if="activeTab === 'audit'" class="h-full overflow-y-auto p-6">
             <AuditTrail />
          </div>

          <div v-else-if="activeTab === 'settings'" class="h-full overflow-y-auto p-6">
             <GlobalSettings />
          </div>

          <!-- Fallback -->
          <div v-else class="h-full overflow-y-auto p-6 flex items-center justify-center">
             <div class="text-gray-500 text-center">
                <div class="text-4xl mb-4">404</div>
                <div>View not found: {{ activeTab }}</div>
             </div>
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
