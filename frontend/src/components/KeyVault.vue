<script setup>
import { Shield, RefreshCw, Lock, Key as KeyIcon, Clock } from 'lucide-vue-next'
import { ref } from 'vue'

const keys = ref([
  { id: 'k1', kid: 'key-us-east-1', region: 'us-east-1', created: '2025-12-01', rotation: '24h', status: 'active' },
  { id: 'k2', kid: 'key-eu-central', region: 'eu-central-1', created: '2026-01-08', rotation: '6h', status: 'active' },
])

const rotateKey = (id) => {
  const k = keys.value.find(x => x.id === id)
  if (k) {
    k.status = 'rotating'
    setTimeout(() => { k.status = 'active'; k.created = new Date().toISOString().split('T')[0] }, 2000)
  }
}
</script>

<template>
  <div class="space-y-8">
    <!-- Header Controls -->
    <div class="flex items-center justify-between border-b border-[#333] pb-6">
       <div>
         <h2 class="text-2xl font-bold">Enterprise KMS Manager</h2>
         <span class="text-xs text-gray-500">Key Lifecycle & Fleet Policy</span>
       </div>
       <div class="flex gap-4">
           <button class="btn btn-secondary text-sm font-bold uppercase tracking-wider">
              Rotate Master Key
           </button>
           <button class="btn btn-primary text-sm font-bold uppercase tracking-wider">
              Provision New Fleet Key
           </button>
       </div>
    </div>

    <!-- KMS Access Policies -->
    <div>
        <h3 class="text-xs font-bold text-gray-500 uppercase mb-4">KMS Access Policies</h3>
        <div class="grid grid-cols-2 gap-6">
            <div class="bg-[#111] border border-[#333] p-6 rounded flex items-center justify-between group hover:border-primary transition-colors">
                <div>
                    <div class="text-xs font-bold text-gray-500 mb-1">Auto-Rotation</div>
                    <div class="text-3xl font-bold text-white mb-2">30d <span class="text-sm text-gray-500 font-normal">TTL</span></div>
                    <div class="text-[10px] text-gray-500">PQC leaf keys are rotated every 30 days automatically.</div>
                </div>
                <div class="text-green-500 font-bold text-xs uppercase bg-green-900/20 px-2 py-1 rounded">Active</div>
            </div>
            <div class="bg-[#111] border border-[#333] p-6 rounded flex items-center justify-between group hover:border-primary transition-colors">
                <div>
                    <div class="text-xs font-bold text-gray-500 mb-1">TEE Attestation</div>
                    <div class="text-3xl font-bold text-white mb-2">Lv. 4 <span class="text-sm text-gray-500 font-normal">HARD</span></div>
                    <div class="text-[10px] text-gray-500">Hardware-backed evidence fabric required for all unwrap calls.</div>
                </div>
                <div class="text-primary font-bold text-xs uppercase bg-primary/20 px-2 py-1 rounded">Enforced</div>
            </div>
        </div>
    </div>

    <!-- Cryptographic Health -->
    <div>
        <h3 class="text-xs font-bold text-gray-500 uppercase mb-4">Cryptographic Health</h3>
        <div class="bg-[#111] border border-[#333] p-8 rounded flex flex-col items-center justify-center">
            
            <!-- CSS Gauge -->
            <div class="relative w-32 h-32 flex items-center justify-center mb-4">
                <svg class="w-full h-full transform -rotate-90">
                    <circle cx="64" cy="64" r="56" stroke="#333" stroke-width="8" fill="transparent" />
                    <circle cx="64" cy="64" r="56" stroke="#00C853" stroke-width="8" fill="transparent" stroke-dasharray="351" stroke-dashoffset="35" class="transition-all duration-1000" />
                </svg>
                <span class="absolute text-2xl font-bold text-white">90%</span>
            </div>

            <div class="text-center">
                <div class="font-bold text-white mb-1">Quantum-Secure Readiness</div>
                <div class="text-xs text-gray-500">9 of 10 active certificates are currently utilizing Post-Quantum algorithms (Dilithium/Kyber).</div>
            </div>
        </div>
    </div>

    <!-- Recent Audit Proofs -->
    <div>
        <h3 class="text-xs font-bold text-gray-500 uppercase mb-4">Recent Audit Proofs</h3>
        <div class="space-y-2">
            <div class="flex items-center justify-between py-2 border-b border-[#333]">
                <div class="flex items-center gap-2">
                    <div class="w-2 h-2 rounded-full bg-green-500"></div>
                    <span class="text-sm font-mono text-gray-300">K7-FLEET: Rotation Signature</span>
                </div>
                <span class="text-xs text-gray-500">2h ago</span>
            </div>
            <div class="flex items-center justify-between py-2 border-b border-[#333]">
                <div class="flex items-center gap-2">
                    <div class="w-2 h-2 rounded-full bg-green-500"></div>
                    <span class="text-sm font-mono text-gray-300">N2-SIG: HSM Policy Sync</span>
                </div>
                <span class="text-xs text-gray-500">5h ago</span>
            </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
.btn {
  @apply px-4 py-2 rounded font-medium transition-colors duration-200 flex items-center inline-flex;
}
.btn-primary {
  @apply bg-orange-600 text-white hover:bg-orange-700;
}
.btn-secondary {
  @apply border border-[#30363d] text-gray-300 hover:text-white hover:bg-[#161b22];
}
.btn-sm {
  @apply px-3 py-1 text-xs;
}
</style>
