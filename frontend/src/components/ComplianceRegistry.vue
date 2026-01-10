<script setup>
import { ShieldCheck, FileCheck, CheckCircle, AlertTriangle } from 'lucide-vue-next'

const profiles = [
  { id: 'tgsp-1', name: 'finance-v2-hardened', version: '2.1.0', status: 'verified', checksum: 'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' },
  { id: 'tgsp-2', name: 'health-hipaa-compliant', version: '1.0.5', status: 'verified', checksum: 'sha256:8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4' },
  { id: 'tgsp-3', name: 'dev-experimental', version: '0.9.0-beta', status: 'warning', checksum: 'sha256:ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb' },
]
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
       <div>
         <h2 class="text-2xl font-bold">Compliance Registry</h2>
         <span class="text-xs text-gray-500">TGSP Profiles & Provenance</span>
       </div>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-3 gap-4">
       <div class="bg-[#161b22] border border-[#30363d] p-4 rounded flex items-center justify-between">
          <div>
            <div class="text-xs text-gray-400">Total Profiles</div>
            <div class="text-2xl font-bold">12</div>
          </div>
          <ShieldCheck class="w-8 h-8 text-green-500 opacity-20" />
       </div>
       <div class="bg-[#161b22] border border-[#30363d] p-4 rounded flex items-center justify-between">
          <div>
            <div class="text-xs text-gray-400">Verified</div>
            <div class="text-2xl font-bold text-green-500">11</div>
          </div>
          <CheckCircle class="w-8 h-8 text-green-500 opacity-20" />
       </div>
       <div class="bg-[#161b22] border border-[#30363d] p-4 rounded flex items-center justify-between">
          <div>
            <div class="text-xs text-gray-400">Warnings</div>
            <div class="text-2xl font-bold text-yellow-500">1</div>
          </div>
          <AlertTriangle class="w-8 h-8 text-yellow-500 opacity-20" />
       </div>
    </div>

    <!-- Table -->
    <div class="bg-[#0d1117] border border-[#30363d] rounded-lg overflow-hidden">
       <table class="w-full text-left text-sm">
          <thead class="bg-[#161b22] text-gray-400 border-b border-[#30363d]">
             <tr>
               <th class="p-4">Profile Name</th>
               <th class="p-4">Version</th>
               <th class="p-4">Checksum (SHA256)</th>
               <th class="p-4">Status</th>
             </tr>
          </thead>
          <tbody>
             <tr v-for="p in profiles" :key="p.id" class="border-b border-[#30363d]/50 hover:bg-[#161b22/50]">
                <td class="p-4 font-medium flex items-center gap-2">
                   <FileCheck class="w-4 h-4 text-gray-500" />
                   {{ p.name }}
                </td>
                <td class="p-4 font-mono text-gray-400">{{ p.version }}</td>
                <td class="p-4 font-mono text-xs text-gray-500">{{ p.checksum.substring(0, 12) }}...</td>
                <td class="p-4">
                   <span class="px-2 py-0.5 rounded textxs font-bold border" 
                         :class="p.status === 'verified' ? 'bg-green-900/20 text-green-400 border-green-900' : 'bg-yellow-900/20 text-yellow-400 border-yellow-900'">
                      {{ p.status.toUpperCase() }}
                   </span>
                </td>
             </tr>
          </tbody>
       </table>
    </div>
  </div>
</template>
