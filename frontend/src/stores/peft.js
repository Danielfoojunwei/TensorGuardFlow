import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const usePeftStore = defineStore('peft', () => {
  const step = ref(1)
  const run = ref({
    status: 'idle', // idle, training, completed, failed
    progress: 0,
    logs: [],
    metrics: { loss: 0, accuracy: 0 }
  })
  
  const config = ref({
    backend: 'local-gpu',
    model: 'llama-3-8b',
    dataset: 'finance-alpaca',
    hparams: {
      lora_r: 16,
      lora_alpha: 32,
      dropout: 0.05
    },
    integrations: {
      wandb: false,
      mlflow: true
    }
  })

  // Mock Actions
  const startRun = async () => {
    run.value.status = 'training'
    run.value.progress = 0
    run.value.logs = []
    
    // Simulate training loop
    let p = 0
    const interval = setInterval(() => {
      p += 5
      run.value.progress = p
      run.value.logs.push(`[TRAIN] Step ${p/5}: Loss=${(Math.random()).toFixed(4)}`)
      
      if (p >= 100) {
        clearInterval(interval)
        run.value.status = 'completed'
        run.value.logs.push('[DONE] Training completed successfully.')
      }
    }, 200)
  }

  const applyProfile = (profileName) => {
    if (profileName === 'local-hf') {
      config.value.backend = 'local-gpu'
      config.value.hparams.lora_r = 64 // High rank for testing
      run.value.logs.push('[CONFIG] Applied Local HF Profile')
    }
  }

  return { 
    step, 
    run, 
    config, 
    startRun, 
    applyProfile 
  }
})
