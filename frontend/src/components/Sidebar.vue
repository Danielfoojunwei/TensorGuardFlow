<script setup>
import { 
  LayoutGrid, Activity, GitBranch, ShieldCheck, Lock, 
  ClipboardList, Server, Settings, Database, Scale, Sliders,
  BookOpen, Search
} from 'lucide-vue-next'
import { ref } from 'vue'

const props = defineProps(['activeTab'])
const emit = defineEmits(['update:activeTab'])

const navItems = [
  { id: 'canvas', label: 'Pipeline Canvas', icon: LayoutGrid }, // N8n Style
  { id: 'performance', label: 'Mission Control', icon: Activity }, // Observability
  { id: 'policy', label: 'Policy Gating', icon: Sliders }, // Tier 3
  { id: 'skills', label: 'Skills Library', icon: BookOpen }, // Tier 2
  { id: 'forensics', label: 'Forensics & CISO', icon: Search }, // Tier 4
  { id: 'peft-studio', label: 'PEFT Studio', icon: Database },
  { id: 'eval', label: 'Eval Arena', icon: Scale },
  { id: 'lineage', label: 'Model Lineage', icon: GitBranch },
  { id: 'compliance', label: 'Compliance Registry', icon: ShieldCheck },
  { id: 'vault', label: 'Key Vault', icon: Lock },
  { id: 'audit', label: 'Audit Trail', icon: ClipboardList },
  { id: 'fleets', label: 'Fleets & Devices', icon: Server },
  { id: 'settings', label: 'Global Settings', icon: Settings },
]
</script>

<template>
  <aside class="w-64 bg-[#000000] border-r border-[#333] fixed h-full z-20 flex flex-col">
    <!-- Logo Area -->
    <div class="h-16 flex items-center px-6 border-b border-[#333]">
       <div class="w-8 h-8 bg-primary rounded mr-3 flex items-center justify-center font-bold text-black">TG</div>
       <span class="font-bold text-lg tracking-tight">TensorGuard</span>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 px-4 space-y-1">
      <template v-for="item in navItems" :key="item.id">
        <button 
          @click="emit('update:activeTab', item.id)"
          class="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors duration-200"
          :class="activeTab === item.id ? 'text-white font-medium bg-[#1f2428] border-l-2 border-[#f78166]' : 'text-gray-400 hover:text-white hover:bg-[#161b22]'"
        >
          <component :is="item.icon" class="w-4 h-4" />
          <span>{{ item.label }}</span>
        </button>
      </template>
    </nav>

    <!-- User Profile -->
    <div class="p-4 border-t border-border mt-auto">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-full bg-[#238636] flex items-center justify-center text-white text-xs font-bold shadow-md">
          DF
        </div>
        <div class="flex flex-col">
          <span class="text-xs font-bold text-white">Daniel Foo</span>
          <span class="text-[10px] text-gray-500">ORG_ADMIN</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
/* GitHub Dark Sidebar Colors */
.bg-sidebar {
  background-color: #0d1117;
}
.border-border {
  border-color: #30363d;
}
</style>
