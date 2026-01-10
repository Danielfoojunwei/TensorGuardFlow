/**
 * TensorGuard Enterprise PLM v2.1 - Frontend Application
 *
 * Comprehensive dashboard with:
 * - Pipeline monitoring and data flow visualization
 * - Key management and rotation tracking
 * - Error console with filtering
 * - System health and degradation status
 * - Version control and model lineage
 */

function app() {
    return {
        // Navigation
        activeTab: 'dashboard',
        currentTime: '',

        // Core Data
        stats: {},
        jobs: [],
        tgspPackages: [],
        runs: [],
        certificates: [],
        endpoints: [],
        auditLogs: [],
        identityJobs: [],

        // System Data (Hardening)
        systemHealth: { status: 'healthy', healthy_count: 0, degraded_count: 0, unhealthy_count: 0, total_count: 0, components: {} },
        systemMetrics: { cpu_usage_percent: 0, memory_usage_percent: 0, disk_usage_percent: 0, thread_count: 0, active_connections: 0, network_bytes_sent: 0, network_bytes_recv: 0 },
        pipelines: [],
        circuits: [],
        openCircuits: [],
        keys: [],
        errors: [],
        errorSummary: { by_level: {}, by_component: {}, total_24h: 0 },
        degradation: { level: 'normal', reason: 'System operating normally', enabled_features: [], disabled_features: [] },
        versionInfo: {},
        modelLineage: { current_version: '', lineage: [] },

        // Robotics VLA & Unification State
        pipelineWorkflow: [],
        keyRotation: { pqc_days_remaining: 0, n2he_hours_remaining: 0, last_rotation: '-' },
        trustPosture: { compliance_health: 0, threat_environment: 'CALIBRATING', at_risk_fleets: 0 },
        fleets: [
            { id: 'f-us-east', name: 'US-East-1 Cluster', region: 'us-east-1', status: 'Healthy', devices_total: 450, devices_online: 442, trust_score: 99.2 },
            { id: 'f-eu-west', name: 'Berlin Gigafactory', region: 'eu-central-1', status: 'Degraded', devices_total: 120, devices_online: 89, trust_score: 84.5 }
        ],
        settings: {
            kms: { provider: 'local', resource_id: '' },
            rtpl: { mode: 'front', profile: 'collaborative' }
        },

        // Computed values
        get pipelineErrors() { return this.pipelines.reduce((sum, p) => sum + p.stages.reduce((s, stage) => s + stage.error_count, 0), 0); },
        get errorCount() { return (this.errorSummary.by_level?.error || 0) + (this.errorSummary.by_level?.warning || 0); },
        get keysNeedingRotation() { return this.keys.filter(k => k.rotation_due).length; },
        errorFilter: { level: '', component: '' },
        get filteredErrors() {
            return this.errors.filter(e => {
                if (this.errorFilter.level && e.level !== this.errorFilter.level) return false;
                if (this.errorFilter.component && e.component !== this.errorFilter.component) return false;
                return true;
            });
        },

        // Initialize
        init() {
            this.updateTime();
            setInterval(() => this.updateTime(), 1000);

            // Fetch Data (Combined)
            this.fetchAll();
            this.fetchPipelineTelemetry(); // From Robotics

            // Initial Graph Render (Robotics)
            setTimeout(() => {
                if (this.renderN8nGraph) this.renderN8nGraph();
            }, 100);

            // Poll every 10s
            setInterval(() => {
                this.fetchAll();
                this.fetchPipelineTelemetry().then(() => {
                    if (this.renderN8nGraph) this.renderN8nGraph();
                });
                if (this.peftStudio.run.status === 'running') {
                    this.peftStudio.actions.pollRun();
                }
            }, 10000);

            // PEFT Init
            try {
                this.fetchPeftConnectors();
                this.fetchPeftProfiles();
            } catch (e) { console.error("Initial PEFT load error", e); }
        },

        // Execute EKU Migration
        async executeEKUMigration() {
            if (!confirm("Proceed with EKU Split Migration for all conflicting certificates? This will trigger automated dual-renewal jobs.")) return;
            // Implementation...
        },

        async fetchSystemHealth() {
            this.loading.health = true;
            try {
                const res = await fetch('/api/v1/system/health');
                if (res.ok) {
                    const data = await res.json();
                    this.systemHealth = {
                        status: data.status,
                        healthy_count: data.healthy_count || 0,
                        degraded_count: data.degraded_count || 0,
                        unhealthy_count: data.unhealthy_count || 0,
                        total_count: data.total_count || 0,
                        components: data.components || {}
                    };
                }
            } catch (e) {
                // Fallback to mock data if API not available
                this.systemHealth = {
                    status: 'healthy',
                    healthy_count: 8,
                    degraded_count: 0,
                    unhealthy_count: 0,
                    total_count: 8,
                    components: {}
                };
            } finally {
                this.loading.health = false;
            }
        },

        async fetchPipelines() {
            this.loading.pipelines = true;
            try {
                const res = await fetch('/api/v1/system/pipeline/status');
                if (res.ok) {
                    this.pipelines = await res.json();
                }
            } catch (e) {
                // Fallback to mock pipeline data
                this.pipelines = [
                    {
                        pipeline_name: 'privacy_pipeline',
                        stages: [
                            { name: 'gradient_clipping', status: 'healthy', latency_ms: 2.3, throughput: 1500, error_count: 0 },
                            { name: 'sparsification', status: 'healthy', latency_ms: 5.1, throughput: 1480, error_count: 0 },
                            { name: 'compression', status: 'healthy', latency_ms: 8.7, throughput: 1450, error_count: 0 },
                            { name: 'encryption', status: 'healthy', latency_ms: 15.2, throughput: 1400, error_count: 0 }
                        ],
                        total_latency_ms: 31.3,
                        success_rate: 99.8,
                        current_throughput: 1400,
                        status: 'healthy'
                    },
                    {
                        pipeline_name: 'aggregation_pipeline',
                        stages: [
                            { name: 'receive', status: 'healthy', latency_ms: 3.2, throughput: 500, error_count: 0 },
                            { name: 'outlier_detection', status: 'healthy', latency_ms: 12.4, throughput: 490, error_count: 0 },
                            { name: 'secure_aggregate', status: 'healthy', latency_ms: 25.6, throughput: 480, error_count: 0 },
                            { name: 'broadcast', status: 'healthy', latency_ms: 8.9, throughput: 475, error_count: 0 }
                        ],
                        total_latency_ms: 50.1,
                        success_rate: 99.5,
                        current_throughput: 475,
                        status: 'healthy'
                    },
                    {
                        pipeline_name: 'identity_pipeline',
                        stages: [
                            { name: 'attestation', status: 'healthy', latency_ms: 45, throughput: 100, error_count: 0 },
                            { name: 'csr_generation', status: 'healthy', latency_ms: 120, throughput: 98, error_count: 0 },
                            { name: 'certificate_issuance', status: 'healthy', latency_ms: 250, throughput: 95, error_count: 0 },
                            { name: 'deployment', status: 'healthy', latency_ms: 80, throughput: 94, error_count: 0 }
                        ],
                        total_latency_ms: 495,
                        success_rate: 98.5,
                        current_throughput: 94,
                        status: 'healthy'
                    }
                ];
            } finally {
                this.loading.pipelines = false;
            }
        },

        async fetchCircuits() {
            try {
                const res = await fetch('/api/v1/system/circuits');
                if (res.ok) {
                    this.circuits = await res.json();
                    this.openCircuits = this.circuits.filter(c => c.state === 'open');
                }
            } catch (e) {
                // Fallback mock data
                this.circuits = [
                    { name: 'aggregator', state: 'closed', failure_rate: 0.01, recent_failures: 1 },
                    { name: 'crypto_service', state: 'closed', failure_rate: 0, recent_failures: 0 },
                    { name: 'identity_provider', state: 'closed', failure_rate: 0.02, recent_failures: 2 },
                    { name: 'network_proxy', state: 'closed', failure_rate: 0, recent_failures: 0 }
                ];
                this.openCircuits = [];
            }
        },

        async fetchKeys() {
            this.loading.keys = true;
            try {
                const res = await fetch('/api/v1/system/keys');
                if (res.ok) {
                    this.keys = await res.json();
                }
            } catch (e) {
                // Fallback mock data
                const now = Date.now() / 1000;
                this.keys = [
                    {
                        key_id: 'aggregation_master_v1',
                        scope: 'aggregation',
                        algorithm: 'N2HE-LWE',
                        created_at: now - 86400 * 7,
                        last_used: now - 60,
                        uses_remaining: 750,
                        rotation_due: false,
                        next_rotation_at: now + 86400 * 23
                    },
                    {
                        key_id: 'identity_signing_v2',
                        scope: 'identity',
                        algorithm: 'Ed25519',
                        created_at: now - 86400 * 30,
                        last_used: now - 300,
                        uses_remaining: 500,
                        rotation_due: false,
                        next_rotation_at: now + 86400 * 60
                    },
                    {
                        key_id: 'inference_context_v1',
                        scope: 'inference',
                        algorithm: 'CKKS',
                        created_at: now - 86400 * 14,
                        last_used: now - 3600,
                        uses_remaining: 200,
                        rotation_due: true,
                        next_rotation_at: now
                    }
                ];
            } finally {
                this.loading.keys = false;
            }
        },

        async fetchErrors() {
            this.loading.errors = true;
            try {
                const [errorsRes, summaryRes] = await Promise.all([
                    fetch('/api/v1/system/errors?limit=100'),
                    fetch('/api/v1/system/errors/summary')
                ]);

                if (errorsRes.ok) {
                    this.errors = await errorsRes.json();
                }
                if (summaryRes.ok) {
                    this.errorSummary = await summaryRes.json();
                }
            } catch (e) {
                // Fallback mock data
                const now = Date.now() / 1000;
                this.errors = [
                    { timestamp: now - 120, level: 'warning', component: 'aggregator', message: 'Client contribution exceeded variance threshold', trace_id: 'trc-8f7e6d5c' },
                    { timestamp: now - 300, level: 'error', component: 'crypto', message: 'Key rotation failed - retrying', trace_id: 'trc-4a3b2c1d' },
                    { timestamp: now - 450, level: 'info', component: 'identity', message: 'Certificate renewal completed', trace_id: 'trc-1a2b3c4d' }
                ];
                this.errorSummary = {
                    by_level: { error: 3, warning: 11, info: 108 },
                    by_component: { aggregator: 18, crypto: 12, identity: 26 },
                    total_24h: 122
                };
            } finally {
                this.loading.errors = false;
            }
        },

        async fetchDegradation() {
            try {
                const res = await fetch('/api/v1/system/degradation');
                if (res.ok) {
                    this.degradation = await res.json();
                }
            } catch (e) {
                this.degradation = {
                    level: 'normal',
                    reason: 'System operating normally',
                    enabled_features: ['encryption', 'aggregation', 'identity', 'network_defense'],
                    disabled_features: []
                };
            }
        },

        async fetchVersions() {
            try {
                const res = await fetch('/api/v1/system/versions');
                if (res.ok) {
                    this.versionInfo = await res.json();
                }
            } catch (e) {
                this.versionInfo = {
                    system_version: '2.1.0',
                    api_version: 'v1',
                    git_commit: '9845eb8',
                    git_branch: 'main',
                    components: {
                        core: '2.1.0',
                        crypto: '2.0.0',
                        agent: '2.1.0',
                        tgsp: '1.0.0',
                        platform: '2.1.0'
                    }
                };
            }
        },

        async fetchLineage() {
            try {
                const res = await fetch('/api/v1/system/lineage');
                if (res.ok) {
                    this.modelLineage = await res.json();
                }
            } catch (e) {
                const now = Date.now() / 1000;
                this.modelLineage = {
                    current_version: 'model_v47',
                    lineage: [
                        { version: 'model_v47', parent: 'model_v46', created_at: now - 3600, clients_contributed: 12, privacy_budget_used: 0.15, validation_score: 0.968 },
                        { version: 'model_v46', parent: 'model_v45', created_at: now - 7200, clients_contributed: 15, privacy_budget_used: 0.12, validation_score: 0.965 },
                        { version: 'model_v45', parent: 'model_v44', created_at: now - 10800, clients_contributed: 8, privacy_budget_used: 0.18, validation_score: 0.962 }
                    ]
                };
            }
        },

        async fetchTelemetry() {
            try {
                const res = await fetch('/api/v1/system/telemetry/system');
                if (res.ok) {
                    const data = await res.json();
                    if (data.history && data.history.length > 0) {
                        this.systemMetrics = data.history[data.history.length - 1];
                    }
                }
            } catch (e) {
                // Fallback with simulated metrics
                this.systemMetrics = {
                    cpu_usage_percent: 35.2 + Math.random() * 10,
                    memory_usage_percent: 62.5 + Math.random() * 5,
                    disk_usage_percent: 45.8,
                    thread_count: 24,
                    active_connections: 8,
                    network_bytes_sent: 1024 * 1024 * 150,
                    network_bytes_recv: 1024 * 1024 * 320
                };
            }
        },

        // === ACTIONS ===

        async rotateKey(keyId) {
            if (!confirm(`Are you sure you want to rotate key "${keyId}"?`)) return;

            try {
                const res = await fetch(`/api/v1/system/keys/${keyId}/rotate`, { method: 'POST' });
                const data = await res.json();
                if (res.ok) {
                    alert(`Key rotation initiated! New key: ${data.new_key_id}`);
                    this.fetchKeys();
                } else {
                    alert(`Rotation failed: ${data.detail || 'Unknown error'}`);
                }
            } catch (e) {
                alert('Key rotation request failed');
            }
        },

        // === FORMATTERS ===

        formatDate(isoStr) {
            if (!isoStr) return '-';
            const d = new Date(isoStr);
            return d.toLocaleTimeString() + ' ' + d.toLocaleDateString();
        },

        formatTimestamp(ts) {
            if (!ts) return '-';
            const d = new Date(ts * 1000);
            return d.toLocaleTimeString() + ' ' + d.toLocaleDateString();
        },

        formatRelativeTime(isoOrMs) {
            if (!isoOrMs) return '-';
            const d = typeof isoOrMs === 'number' ? new Date(isoOrMs) : new Date(isoOrMs);
            const now = new Date();
            const diff = Math.floor((now - d) / 1000);

            if (diff < 60) return `${diff}s ago`;
            if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
            if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
            return `${Math.floor(diff / 86400)}d ago`;
        },

        formatBytes(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        },

        getStatusColor(status) {
<<<<<<< HEAD
            const colors = {
                'completed': 'text-emerald-400',
                'evaluated': 'text-sky-400',
                'running': 'text-amber-400',
                'failed': 'text-red-400',
                'pending': 'text-white/40',
                'registered': 'text-violet-400',
                'succeeded': 'text-emerald-400',
                'issuing': 'text-sky-300 animate-pulse',
                'deploying': 'text-amber-400',
                'validating': 'text-indigo-400',
                'verified': 'text-emerald-400',
                'healthy': 'text-emerald-400',
                'unhealthy': 'text-red-400',
                'degraded': 'text-amber-400'
            };
            return colors[status?.toLowerCase()] || 'text-white/40';
        },

        getStatusBg(status) {
            const colors = {
                'completed': 'bg-emerald-500/20',
                'evaluated': 'bg-sky-500/20',
                'running': 'bg-amber-500/20',
                'failed': 'bg-red-500/20',
                'pending': 'bg-white/10',
                'registered': 'bg-violet-500/20',
                'succeeded': 'bg-emerald-500/20',
                'issuing': 'bg-sky-500/20',
                'deploying': 'bg-amber-500/20',
                'validating': 'bg-indigo-500/20',
                'verified': 'bg-emerald-500/20',
                'healthy': 'bg-emerald-500/20',
                'unhealthy': 'bg-red-500/20',
                'degraded': 'bg-amber-500/20'
            };
            return colors[status?.toLowerCase()] || 'bg-white/10';
=======
            const s = status?.toLowerCase();
            if (['failed', 'error', 'revoked'].includes(s)) return 'text-orange-500 font-bold';
            if (['running', 'active', 'validating'].includes(s)) return 'text-orange-300 animate-pulse';
            if (['completed', 'succeeded', 'registered'].includes(s)) return 'text-white font-medium';
            return 'text-[#666]';
        },

        getStatusBg(status) {
            const s = status?.toLowerCase();
            if (['failed', 'error', 'revoked'].includes(s)) return 'bg-orange-500/20';
            if (['running', 'active', 'validating'].includes(s)) return 'bg-orange-500/10';
            if (['completed', 'succeeded', 'registered'].includes(s)) return 'bg-white/10';
            return 'bg-[#222]';
>>>>>>> 5a99ad8 (feat: realign N8n, Eval Arena, and PEFT for Robotics VLA workflows)
        },

        getCertExpiryClass(daysToExpiry) {
            if (daysToExpiry <= 7) return 'text-orange-500 bg-orange-500/20 font-bold';
            if (daysToExpiry <= 30) return 'text-orange-300 bg-orange-500/10';
            return 'text-white bg-white/10';
        },

        renderN8nGraph() {
            const canvas = document.getElementById('n8n-canvas');
            if (!canvas) return;

            // Clear existing nodes (keep SVG layer)
            const htmlNodes = canvas.querySelectorAll('.graph-node');
            htmlNodes.forEach(n => n.remove());

            const svgLayer = canvas.querySelector('.connector-layer');
            svgLayer.innerHTML = ''; // Clear paths

            // Telemetry Data (or Fallback)
            const data = this.pipelineWorkflow || {
                nodes: [
                    { id: 'edge', label: 'Pi0 Edge Device', type: 'source', status: 'active', x: 50, y: 150, metrics: { cpu: '45%', ram: '1.2GB', fps: '30' } },
                    { id: 'agg', label: 'Aggregation Server', type: 'process', status: 'active', x: 350, y: 150, metrics: { clients: 12, round: 42, latency: '12ms' } },
                    { id: 'cloud', label: 'Cloud Backend', type: 'target', status: 'active', x: 650, y: 150, metrics: { uptime: '99.9%', cost: '$0.42/h', model: 'Llama-3' } }
                ]
            };

            // 1. Render Nodes
            data.nodes.forEach(node => {
                const el = document.createElement('div');
                el.className = `graph-node ${node.status === 'stopped' ? 'opacity-50 grayscale' : ''}`;
                el.style.left = node.x + 'px';
                el.style.top = node.y + 'px';
                el.style.cursor = 'pointer';

                // Add click handler for Modal
                el.onclick = () => {
                    this.modal.node = node;
                    this.modal.open = true;
                };

                el.innerHTML = `
                    <div class="node-header">
                        <span>${node.label}</span>
                        <i data-lucide="${node.type === 'source' ? 'cpu' : (node.type === 'target' ? 'cloud' : 'layers')}" class="w-3 h-3"></i>
                    </div>
                    <div class="node-body">
                        ${Object.entries(node.metrics).map(([k, v]) => `
                            <div class="node-metric">
                                <span class="uppercase opacity-50">${k}</span>
                                <span>${v}</span>
                            </div>
                        `).join('')}
                    </div>
                    ${node.status === 'stopped' ? '<div class="absolute inset-0 flex items-center justify-center bg-black/50 text-red-500 font-bold uppercase tracking-widest text-xs">STOPPED</div>' : ''}
                `;
                canvas.appendChild(el);
            });

            // 2. Render Connections (Bezier)
            const nodes = data.nodes;
            for (let i = 0; i < nodes.length - 1; i++) {
                const src = nodes[i];
                const tgt = nodes[i + 1];

                // Calculate anchor points (Right of Src -> Left of Tgt)
                const x1 = src.x + 160;
                const y1 = src.y + 40;
                const x2 = tgt.x;
                const y2 = tgt.y + 40;

                // Bezier Control Points
                const cp1x = x1 + (x2 - x1) / 2;
                const cp2x = x2 - (x2 - x1) / 2;

                const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
                path.setAttribute("d", `M ${x1} ${y1} C ${cp1x} ${y1}, ${cp2x} ${y2}, ${x2} ${y2}`);
                path.setAttribute("class", "connector-path active");
                svgLayer.appendChild(path);
            }

            // Re-init Icons for new nodes
            if (window.lucide) window.lucide.createIcons();
        },

        async fetchPeftConnectors() {
            try {
                const res = await fetch('/api/v1/peft/connectors');
                if (res.ok) this.peftStudio.connectors = await res.json();
            } catch (e) { }
        },

        async fetchPeftProfiles() {
            try {
                const res = await fetch('/api/v1/peft/profiles');
                if (res.ok) this.peftStudio.profiles = await res.json();
            } catch (e) { }
        }
    }
}
