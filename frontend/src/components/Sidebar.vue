<script setup>
import {
  LayoutGrid, Activity, GitBranch, ShieldCheck, Lock,
  ClipboardList, Server, Settings, Database, Scale, Sliders,
  BookOpen, Search, Bot, FileKey, Link, Package, Radio
} from 'lucide-vue-next'

const props = defineProps(['activeTab'])
const emit = defineEmits(['update:activeTab'])

const navSections = [
  {
    title: 'Core',
    items: [
      { id: 'canvas', label: 'Pipeline Canvas', icon: LayoutGrid },
      { id: 'monitor', label: 'Training Monitor', icon: Radio },
      { id: 'performance', label: 'Mission Control', icon: Activity },
    ]
  },
  {
    title: 'Models & Training',
    items: [
      { id: 'vla-registry', label: 'VLA Registry', icon: Bot },
      { id: 'peft-studio', label: 'PEFT Studio', icon: Database },
      { id: 'eval', label: 'Eval Arena', icon: Scale },
      { id: 'skills', label: 'Skills Library', icon: BookOpen },
    ]
  },
  {
    title: 'Security & Identity',
    items: [
      { id: 'identity', label: 'Identity Manager', icon: FileKey },
      { id: 'vault', label: 'Key Vault', icon: Lock },
      { id: 'policy', label: 'Policy Gating', icon: Sliders },
      { id: 'forensics', label: 'Forensics & CISO', icon: Search },
    ]
  },
  {
    title: 'Deployment & Ops',
    items: [
      { id: 'tgsp-marketplace', label: 'TGSP Marketplace', icon: Package },
      { id: 'integrations', label: 'Integrations Hub', icon: Link },
      { id: 'fleets', label: 'Fleets & Devices', icon: Server },
      { id: 'lineage', label: 'Model Lineage', icon: GitBranch },
    ]
  },
  {
    title: 'Compliance',
    items: [
      { id: 'compliance', label: 'Compliance Registry', icon: ShieldCheck },
      { id: 'audit', label: 'Audit Trail', icon: ClipboardList },
      { id: 'settings', label: 'Global Settings', icon: Settings },
    ]
  }
]
</script>

<template>
  <aside class="w-64 bg-[#000000] border-r border-[#333] fixed h-full z-20 flex flex-col overflow-hidden">
    <!-- Logo Area -->
    <div class="h-16 flex items-center px-6 border-b border-[#333] flex-shrink-0">
       <div class="w-8 h-8 bg-primary rounded mr-3 flex items-center justify-center font-bold text-black">TG</div>
       <span class="font-bold text-lg tracking-tight">TensorGuard</span>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 px-3 py-4 overflow-y-auto">
      <template v-for="(section, sIdx) in navSections" :key="section.title">
        <!-- Section Header -->
        <div v-if="sIdx > 0" class="mt-4 mb-2 px-3">
          <span class="text-[10px] font-bold text-gray-600 uppercase tracking-wider">{{ section.title }}</span>
        </div>
        <div v-else class="mb-2 px-3">
          <span class="text-[10px] font-bold text-gray-600 uppercase tracking-wider">{{ section.title }}</span>
        </div>

        <!-- Section Items -->
        <div class="space-y-0.5">
          <button
            v-for="item in section.items"
            :key="item.id"
            @click="emit('update:activeTab', item.id)"
            class="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors duration-200"
            :class="activeTab === item.id
              ? 'text-white font-medium bg-[#1f2428] border-l-2 border-[#f78166]'
              : 'text-gray-400 hover:text-white hover:bg-[#161b22]'"
          >
            <component :is="item.icon" class="w-4 h-4 flex-shrink-0" />
            <span class="truncate">{{ item.label }}</span>
          </button>
        </div>
      </template>
    </nav>

    <!-- User Profile -->
    <div class="p-4 border-t border-[#333] flex-shrink-0">
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
/* Custom scrollbar for sidebar */
nav::-webkit-scrollbar {
  width: 4px;
}
nav::-webkit-scrollbar-track {
  background: transparent;
}
nav::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}
nav::-webkit-scrollbar-thumb:hover {
  background: #444;
}
</style>
