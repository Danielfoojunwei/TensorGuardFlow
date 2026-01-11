import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useSimulationStore = defineStore('simulation', () => {
    // --- State ---
    const activeFleetId = ref('f1')
    const roundStatus = ref('idle')
    const currentRound = ref(42)
    const lastMetrics = ref({ loss: 0.142, accuracy: 89.4, throughput: '4.2GB/s' })

    // Static Infrastructure Nodes
    const infraNodes = [
        {
            id: 'infra-gateway',
            label: 'Fleet Gateway',
            type: 'aggregator', // Visual style
            status: 'success',
            icon: 'server',
            subtitle: 'Region: US-East-1',
            position: { x: 400, y: 150 }, // Top Center
            data: { details: { metric: 'Active Connections', value: '452', unit: '' } }
        },
        {
            id: 'infra-global',
            label: 'Global Model Registry',
            type: 'security', // Visual style
            status: 'success',
            icon: 'database',
            subtitle: 'Production v2.4',
            position: { x: 1400, y: 300 }, // Far Right
            data: { details: { metric: 'Model Size', value: '1.2', unit: 'GB' } }
        }
    ]

    const devices = ref([
        { id: 'dev-001', name: 'UR5e-Alpha', fleet: 'f1', status: 'online', trust: 98, last_update: '2s ago' },
        { id: 'dev-002', name: 'Franka-Beta', fleet: 'f1', status: 'training', trust: 95, last_update: '15s ago' },
        { id: 'dev-003', name: 'Kuka-Gamma', fleet: 'f1', status: 'idle', trust: 99, last_update: '5m ago' },
    ])

    // Fixed 7-Stage Pipeline Structure (Center Bus)
    const pipelineSteps = [
        {
            id: 'p-trigger',
            label: 'Trigger',
            type: 'trigger',
            status: 'idle',
            details: { metric: 'Events', value: '124', unit: '/min' }
        },
        {
            id: 'p-clip',
            label: 'Gradient Clip',
            type: 'action',
            status: 'idle',
            details: { metric: 'L2 Norm', value: '0.98', unit: 'avg' }
        },
        {
            id: 'p-sparse',
            label: 'Rand-K Sparsify',
            type: 'action',
            status: 'idle',
            details: { metric: 'Reduction', value: '99.2', unit: '%' }
        },
        {
            id: 'p-enc',
            label: 'Encrypt (N2HE)',
            type: 'security',
            status: 'idle',
            details: { metric: 'Overhead', value: '12', unit: 'ms' }
        },
        {
            id: 'p-agg',
            label: 'Aggregator',
            type: 'aggregator',
            status: 'idle',
            details: { metric: 'Quorum', value: '3/3', unit: 'OK' }
        },
        {
            id: 'p-eval',
            label: 'Eval Gate',
            type: 'aggregator',
            status: 'idle',
            details: { metric: 'Score', value: '0.89', unit: 'AP' }
        },
        {
            id: 'p-deploy',
            label: 'Deploy Update',
            type: 'aggregator',
            status: 'idle',
            details: { metric: 'Version', value: 'v2.4', unit: '' }
        },
    ]

    const activeSteps = ref([...pipelineSteps])

    // --- Actions ---
    const enrollDevice = () => {
        const id = `dev-${Date.now().toString().slice(-4)}`
        devices.value.push({
            id,
            name: `Robot-${id}`,
            fleet: activeFleetId.value,
            status: 'provisioning',
            trust: 100,
            last_update: 'Just now'
        })
    }

    const startRound = () => {
        if (roundStatus.value !== 'idle') return

        // Animation Sequence: Devices -> Gateway -> Pipeline -> Global
        roundStatus.value = 'collecting'

        // 1. Devices to Gateway (Simulated delay)
        setTimeout(() => {
            // 2. Start Pipeline
            runStep('p-trigger', 'training', 800, { metric: 'Events', value: '256' })
                .then(() => runStep('p-clip', 'processing', 600, { metric: 'L2 Norm', value: '0.92' }))
                .then(() => runStep('p-sparse', 'processing', 600, { metric: 'Reduction', value: '99.8%' }))
                .then(() => runStep('p-enc', 'encrypting', 1000, { metric: 'Overhead', value: '18ms' }))
                .then(() => runStep('p-agg', 'aggregating', 1200, { metric: 'Quorum', value: '5/5' }))
                .then(() => runStep('p-eval', 'verifying', 800, { metric: 'Score', value: '0.92' }))
                .then(() => runStep('p-deploy', 'updating', 800, { metric: 'Version', value: 'v2.5' }))
                .then(() => {
                    roundStatus.value = 'idle'
                    currentRound.value++
                    lastMetrics.value.loss = Math.max(0.05, lastMetrics.value.loss - 0.005).toFixed(3)
                    lastMetrics.value.accuracy = Math.min(99.9, lastMetrics.value.accuracy + 0.5).toFixed(1)
                    resetSteps()
                })
        }, 1000)
    }

    const runStep = (stepId, statusLabel, duration, newDetails = null) => {
        return new Promise(resolve => {
            roundStatus.value = statusLabel
            const step = activeSteps.value.find(s => s.id === stepId)
            if (step) {
                step.status = 'running'
                if (newDetails) {
                    step.details.value = newDetails.value
                    if (newDetails.unit) step.details.unit = newDetails.unit
                }
                setTimeout(() => {
                    step.status = 'success'
                    resolve()
                }, duration)
            } else {
                resolve()
            }
        })
    }

    const resetSteps = () => {
        activeSteps.value.forEach(s => s.status = 'idle')
    }

    // --- GettersForGraph ---
    const graphNodes = computed(() => {
        const nodes = []

        // 1. Infrastructure
        infraNodes.forEach(infra => {
            nodes.push({
                id: infra.id,
                type: 'pipeline',
                position: infra.position,
                data: { ...infra, ...infra.data }
            })
        })

        // 2. Devices (Left Orbit)
        devices.value.filter(d => d.fleet === activeFleetId.value).forEach((dev, idx) => {
            nodes.push({
                id: dev.id,
                type: 'pipeline',
                position: { x: 50, y: 100 + (idx * 220) }, // Left Stack
                data: {
                    label: dev.name,
                    type: 'trigger',
                    icon: 'play',
                    subtitle: dev.status,
                    status: dev.status === 'training' ? 'running' : (dev.status === 'online' ? 'success' : 'idle'),
                    details: { metric: 'Trust', value: dev.trust, unit: '%' }
                }
            })
        })

        // 3. Pipeline (Center Horizontal Bus) - Shifted Down
        let xOffset = 400
        activeSteps.value.forEach((step, idx) => {
            // Determine Grid Layout (Wrap if needed, but horizontal usually fits 7)
            // We'll do a simple horizontal bus below the Gateway
            const isAgg = idx >= 4 // Shift aggregators slightly or keep straight
            nodes.push({
                id: step.id,
                type: 'pipeline',
                position: { x: 400 + (idx * 300), y: 450 }, // Row at Y=450
                data: { ...step, subtitle: step.status.toUpperCase(), round: currentRound.value }
            })
        })

        return nodes
    })

    // Edges - Orthogonal Routing
    const graphEdges = computed(() => {
        const edges = []

        // 1. Devices -> Gateway (Step)
        devices.value.forEach(dev => {
            edges.push({
                id: `e-${dev.id}-gateway`,
                source: dev.id,
                target: 'infra-gateway',
                animated: dev.status === 'training' || roundStatus.value === 'collecting',
                style: { stroke: '#30363d', strokeWidth: 2 },
                type: 'step' // Orthogonal
            })
        })

        // 2. Gateway -> Trigger (First Step)
        edges.push({
            id: 'e-gateway-trigger',
            source: 'infra-gateway',
            target: 'p-trigger',
            animated: roundStatus.value === 'collecting' || roundStatus.value === 'training',
            style: { stroke: '#30363d', strokeWidth: 2 },
            type: 'step'
        })

        // 3. Pipeline Chain
        for (let i = 0; i < activeSteps.value.length - 1; i++) {
            const current = activeSteps.value[i]
            const next = activeSteps.value[i + 1]
            edges.push({
                id: `e-${current.id}-${next.id}`,
                source: current.id,
                target: next.id,
                animated: current.status === 'success' || current.status === 'running',
                style: {
                    stroke: current.status === 'running' ? '#ff6d5a' : '#30363d',
                    strokeWidth: current.status === 'running' ? 3 : 2
                },
                type: 'step' // Orthogonal
            })
        }

        // 4. Deploy -> Global Model
        edges.push({
            id: 'e-deploy-global',
            source: 'p-deploy',
            target: 'infra-global',
            animated: roundStatus.value === 'updating',
            style: { stroke: '#30363d', strokeWidth: 2 },
            type: 'step'
        })

        return edges
    })

    return {
        activeFleetId,
        roundStatus,
        currentRound,
        lastMetrics,
        devices,
        activeSteps,
        graphNodes,
        graphEdges,
        enrollDevice,
        startRound
    }
})
