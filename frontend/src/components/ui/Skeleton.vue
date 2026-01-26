<script setup>
/**
 * Skeleton Loading Component
 *
 * Provides visual placeholders during data loading:
 * - Card skeleton for dashboard widgets
 * - Table skeleton for data tables
 * - Text skeleton for content
 */
const props = defineProps({
    variant: {
        type: String,
        default: 'text',
        validator: (v) => ['text', 'card', 'table', 'avatar', 'button'].includes(v)
    },
    lines: {
        type: Number,
        default: 3
    },
    rows: {
        type: Number,
        default: 5
    }
})
</script>

<template>
  <!-- Text skeleton -->
  <div v-if="variant === 'text'" class="space-y-2">
    <div
      v-for="i in lines"
      :key="i"
      :class="[
        'h-4 bg-[#1f2428] rounded animate-pulse',
        i === lines ? 'w-3/4' : 'w-full'
      ]"
    ></div>
  </div>

  <!-- Card skeleton -->
  <div v-else-if="variant === 'card'" class="bg-[#0d1117] border border-[#30363d] rounded-lg p-5">
    <div class="flex items-center justify-between mb-4">
      <div class="w-8 h-8 bg-[#1f2428] rounded animate-pulse"></div>
      <div class="w-16 h-3 bg-[#1f2428] rounded animate-pulse"></div>
    </div>
    <div class="w-24 h-8 bg-[#1f2428] rounded animate-pulse mb-2"></div>
    <div class="w-32 h-3 bg-[#1f2428] rounded animate-pulse"></div>
  </div>

  <!-- Table skeleton -->
  <div v-else-if="variant === 'table'" class="bg-[#0d1117] border border-[#30363d] rounded-lg overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-4 px-5 py-3 border-b border-[#30363d] bg-[#161b22]">
      <div class="w-1/4 h-3 bg-[#1f2428] rounded animate-pulse"></div>
      <div class="w-1/4 h-3 bg-[#1f2428] rounded animate-pulse"></div>
      <div class="w-1/4 h-3 bg-[#1f2428] rounded animate-pulse"></div>
      <div class="w-1/4 h-3 bg-[#1f2428] rounded animate-pulse"></div>
    </div>
    <!-- Rows -->
    <div v-for="i in rows" :key="i" class="flex items-center gap-4 px-5 py-4 border-b border-[#30363d] last:border-0">
      <div class="w-1/4 h-4 bg-[#1f2428] rounded animate-pulse"></div>
      <div class="w-1/4 h-4 bg-[#1f2428] rounded animate-pulse"></div>
      <div class="w-1/4 h-4 bg-[#1f2428] rounded animate-pulse"></div>
      <div class="w-1/4 h-4 bg-[#1f2428] rounded animate-pulse"></div>
    </div>
  </div>

  <!-- Avatar skeleton -->
  <div v-else-if="variant === 'avatar'" class="w-10 h-10 rounded-full bg-[#1f2428] animate-pulse"></div>

  <!-- Button skeleton -->
  <div v-else-if="variant === 'button'" class="w-24 h-9 bg-[#1f2428] rounded-lg animate-pulse"></div>
</template>
