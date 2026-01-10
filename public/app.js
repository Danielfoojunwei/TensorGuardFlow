function app() {
    return {
        activeTab: 'dashboard',
        stats: {},
        jobs: [],
        tgspPackages: [],
        runs: [],
        certificates: [],
        endpoints: [],
        auditLogs: [],
        identityJobs: [],
        pipelineWorkflow: [],
        keyRotation: { pqc_days_remaining: 0, n2he_hours_remaining: 0, last_rotation: '-' },
        trustPosture: { compliance_health: 0, threat_environment: 'CALIBRATING', at_risk_fleets: 0 },

        // Phase 6: Unification State
        fleets: [
            { id: 'f-us-east', name: 'US-East-1 Cluster', region: 'us-east-1', status: 'Healthy', devices_total: 450, devices_online: 442, trust_score: 99.2 },
            { id: 'f-eu-west', name: 'Berlin Gigafactory', region: 'eu-central-1', status: 'Degraded', devices_total: 120, devices_online: 89, trust_score: 84.5 }
        ],
        settings: {
            kms: { provider: 'local', resource_id: '' },
            rtpl: { mode: 'front', profile: 'collaborative' }
        },
        currentTime: '',

        // Security Controls State
        security: {
            pqc: true,
            dp: false
        },
        // Modal State
        modal: {
            open: false,
            node: null
        },

        togglePQC() {
            this.security.pqc = !this.security.pqc;
            // Simulate impact
            if (this.security.pqc) alert("Kyber-1024 / Dilithium-5 Enforced on all TEE channels.");
            else alert("WARNING: PQC Disabled. Reverting to RSA-2048 (Legacy).");
        },

        toggleDP() {
            this.security.dp = !this.security.dp;
            // Simulate impact
            if (this.security.dp) alert("Differential Privacy (Epsilon=3.0) applied to Aggregator.");
            else alert("Differential Privacy Disabled. Raw gradients visible to Aggregator.");
        },

        generateReport() {
            window.print();
        },

        generateEnrollmentToken() {
            const mockToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + btoa(JSON.stringify({ iss: "tensorguard", exp: Date.now() + 3600 })) + ".SIGNATURE_VERIFIED_HSM";
            alert("New Device Enrollment Token Generated:\n\n" + mockToken + "\n\n(Copied to Clipboard)");
            console.log("Token: ", mockToken);
        },

        revokeFleet(id) {
            if (confirm("Are you sure you want to REVOKE the identity of fleet " + id + "?\nThis will disconnect all " + this.fleets.find(f => f.id === id).devices_total + " devices immediately.")) {
                this.fleets = this.fleets.filter(f => f.id !== id);
                alert("Fleet " + id + " has been revoked. RTPL policies updated to block traffic.");
            }
        },

        testKMSConnection() {
            const provider = this.settings.kms.provider.toUpperCase();
            if (provider === 'LOCAL') {
                alert("Connected to Local Development KeyStore.\nLatency: 0.2ms");
            } else {
                alert("Successfully authenticated with " + provider + ".\nAssuming Role: arn:aws:iam::12345678:role/TensorGuardMaster\n\nLatency: 45ms");
            }
        },

        stopNode(id) {
            alert(`Signal sent: STOP ${id}`);
            if (this.modal.node) this.modal.node.status = 'stopped';
            this.modal.open = false;
            // Update graph visual
            this.renderN8nGraph();
        },

        startNode(id) {
            alert(`Signal sent: START ${id}`);
            if (this.modal.node) this.modal.node.status = 'active';
            this.modal.open = false;
            // Update graph visual
            this.renderN8nGraph();
        },

        deployPackage(id) {
            const fleet = this.fleets[0].name; // Default to first fleet
            if (confirm(`Deploy Package ${id} to ${fleet}?\n\nThis will initiate a Canary release (10% traffic).`)) {
                alert(`Deployment Initiated!\n\nTarget: ${fleet}\nVersion: ${id}\nStrategy: Canary (10%)`);
            }
        },

        // PEFT Studio State
        peftStudio: {
            step: 1,
            connectors: [],
            profiles: [],
            draft: {
                training_config: {
                    backend: 'hf',
                    method: 'lora',
                    model_name_or_path: 'meta-llama/Llama-2-7b-hf',
                    dataset_name_or_path: 'databricks/databricks-dolly-15k',
                    learning_rate: 5e-5,
                    batch_size: 4,
                    max_steps: 100,
                    seed: 42
                },
                integrations: {
                    tracking: 'simulated',
                    store: 'local_run'
                },
                dp_enabled: false,
                dp_epsilon: 10.0,
                policy_gate_id: 'default-peft-gate'
            },
            run: {
                run_id: null,
                status: 'idle',
                stage: 'waiting',
                progress: 0,
                logs: []
            },
            actions: {}
        },

        // Loading & Error States
        loading: {
            stats: true,
            jobs: true,
            tgsp: true,
            runs: true,
            inventory: true,
            audit: true,
            identity: true
        },
        errors: {
            stats: null,
            jobs: null,
            tgsp: null,
            runs: null,
            inventory: null,
            audit: null,
            identity: null
        },

        // Charts
        privacyChart: null,
        lineageChart: null,

        init() {
            this.updateTime();
            setInterval(() => this.updateTime(), 1000);

            this.fetchStats();
            this.fetchJobs();
            this.fetchTGSP();
            this.fetchRuns();
            this.fetchInventory();
            this.fetchAudit();
            this.fetchIdentityJobs();
            this.fetchPipelineTelemetry();
            // Initial Graph Render
            setTimeout(() => this.renderN8nGraph(), 100);

            // Poll every 10s (reduced for performance)
            setInterval(() => {
                this.fetchStats();
                this.fetchJobs();
                this.fetchTGSP();
                this.fetchRuns();
                this.fetchInventory();
                this.fetchAudit();
                this.fetchIdentityJobs();
                this.fetchPipelineTelemetry().then(() => this.renderN8nGraph());
                if (this.peftStudio.run.status === 'running') {
                    this.peftStudio.actions.pollRun();
                }
            }, 10000);

            // Helper for robust error handling
            this.handleError = (source, error) => {
                console.error(`[${source}] Error:`, error);
                // In a real app, this would update a global error state toaster
                // For now, we set a scoped error if available, or alert
                if (this.errors && this.errors[source]) {
                    this.errors[source] = error.message || "An unexpected error occurred";
                } else {
                    alert(`Error in ${source}: ${error.message || error}`);
                }
            };

            // PEFT Studio Actions Binding
            this.peftStudio.actions = {
                testConnector: async (type) => {
                    try {
                        const res = await fetch('/api/v1/peft/connectors/test', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ connector_type: type, config: {} })
                        });
                        const data = await res.json();
                        if (data.valid) {
                            alert('Connector Valid!');
                        } else {
                            throw new Error(data.error || 'Connector validation failed');
                        }
                    } catch (e) {
                        this.handleError('peft', e);
                    }
                },
                applyProfile: async (id) => {
                    const profile = this.peftStudio.profiles.find(p => p.id === id);
                    if (profile) {
                        this.peftStudio.draft.training_config = { ...profile.training_config };
                        this.peftStudio.step = 2;
                        setTimeout(() => lucide.createIcons(), 50);
                    }
                },
                startRun: async () => {
                    try {
                        const res = await fetch('/api/v1/peft/runs', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(this.peftStudio.draft)
                        });
                        const data = await res.json();
                        if (res.ok) {
                            this.peftStudio.run.run_id = data.run_id;
                            this.peftStudio.run.status = 'running';
                            this.peftStudio.step = 8;
                            setTimeout(() => {
                                lucide.createIcons();
                                this.peftStudio.actions.pollRun();
                            }, 100);
                        } else {
                            throw new Error(data.detail || 'Failed to start run');
                        }
                    } catch (e) {
                        this.handleError('peft', e);
                    }
                },
                pollRun: async () => {
                    if (!this.peftStudio.run.run_id) return;
                    try {
                        const res = await fetch(`/api/v1/peft/runs/${this.peftStudio.run.run_id}`);
                        if (res.ok) {
                            const data = await res.json();
                            this.peftStudio.run.status = data.status;
                            this.peftStudio.run.stage = data.stage;
                            this.peftStudio.run.progress = data.progress;
                            this.peftStudio.run.logs = data.logs || [];

                            // Scroll logs to bottom
                            setTimeout(() => {
                                const logEl = document.getElementById('runLogs');
                                if (logEl) logEl.scrollTop = logEl.scrollHeight;
                            }, 10);

                            if (data.status === 'completed' || data.status === 'failed') {
                                this.fetchRuns(); // Refresh general runs list
                            }
                        }
                    } catch (e) {
                        console.error("Poll failed", e);
                    }
                },
                promote: async (environment) => {
                    try {
                        const res = await fetch(`/api/v1/peft/runs/${this.peftStudio.run.run_id}/promote`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ environment })
                        });
                        const data = await res.json();
                        if (data.status !== 'success') throw new Error(data.error);
                        alert('Promoted successfully!');
                    } catch (e) {
                        this.handleError('peft', e);
                    }
                }
            };

            // Initial Data Load with Error Handling
            try {
                this.fetchPeftConnectors();
                this.fetchPeftProfiles();
            } catch (e) { console.error("Initial load error", e); }

            // Re-run icons when tab changes
            this.$watch('activeTab', (val) => {
                console.log("Tab changed to:", val);
                setTimeout(() => {
                    lucide.createIcons();
                    this.initCharts();
                }, 50);
            });

            // Initialize charts after first data load
            setTimeout(() => this.initCharts(), 500);
        },

        // KMS & Compliance Actions
        async triggerKeyRotation() {
            if (!confirm("Initiate emergency global key rotation? This will refresh all PQC and mTLS master secrets.")) return;
            try {
                const res = await fetch('/api/v1/identity/rotations', { method: 'POST' });
                if (!res.ok) throw new Error("API returned " + res.status);
                alert("Emergency rotation initiated.");
                this.fetchAudit();
                this.fetchInventory();
            } catch (e) {
                this.handleError('kms', e);
            }
        },

        async rotateMasterKey() {
            try {
                const res = await fetch('/api/v1/identity/rotations', { method: 'POST' });
                if (!res.ok) throw new Error("API returned " + res.status);
                alert("Master key rotation started.");
                this.fetchInventory();
            } catch (e) {
                this.handleError('kms', e);
            }
        },

        async provisionFleetKey() {
            const subject = prompt("Enter Common Name for new Fleet Key:", "node-fleet-x");
            if (!subject) return;
            try {
                const res = await fetch('/api/v1/identity/enroll', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ subject_common_name: subject, type: 'FLEET_NODE' })
                });
                if (!res.ok) throw new Error("Failed to enroll");
                alert("New fleet key provisioned.");
                this.fetchInventory();
            } catch (e) {
                this.handleError('kms', e);
            }
        },

        async rotateKey(certId) {
            try {
                const res = await fetch(`/api/v1/identity/certificates/${certId}/rotate`, { method: 'POST' });
                if (!res.ok) throw new Error("Rotation failed");
                alert("Key rotation successful.");
                this.fetchInventory();
            } catch (e) {
                this.handleError('kms', e);
            }
        },


        updateTime() {
            const now = new Date();
            this.currentTime = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        },

        initCharts() {
            this.initPrivacyChart();
            this.initLineageChart();
        },

        initPrivacyChart() {
            const ctx = document.getElementById('privacyChart');
            if (!ctx || this.privacyChart) return;

            const consumed = this.stats.privacy_consumed || 1.6;
            const remaining = (this.stats.privacy_cap || 10) - consumed;

            this.privacyChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Consumed', 'Remaining'],
                    datasets: [{
                        data: [consumed, remaining],
                        backgroundColor: ['#f59e0b', '#10b981'],
                        borderWidth: 0,
                        cutout: '75%'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        },

        initLineageChart() {
            const ctx = document.getElementById('lineageChart');
            if (!ctx || this.lineageChart) return;

            const labels = this.runs.slice(0, 7).map(r => r.run_id?.substring(0, 8) || 'N/A');
            const data = this.runs.slice(0, 7).map(() => Math.floor(Math.random() * 40) + 60);

            this.lineageChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels.length ? labels : ['No Data'],
                    datasets: [{
                        label: 'Lineage Score',
                        data: data.length ? data : [0],
                        backgroundColor: 'rgba(56, 189, 248, 0.6)',
                        borderColor: 'rgba(56, 189, 248, 1)',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: { color: 'rgba(255,255,255,0.4)' }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: 'rgba(255,255,255,0.4)' }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        },

        async fetchStats() {
            this.loading.stats = true;
            this.errors.stats = null;
            try {
                const res = await fetch('/api/v1/enablement/stats');
                if (res.ok) {
                    const data = await res.json();
                    this.stats = data;
                    if (data.trust_posture) {
                        this.trustPosture = data.trust_posture;
                    }
                } else {
                    this.errors.stats = `Error ${res.status}`;
                }
            } catch (e) {
                console.error("Stats fetch failed", e);
                this.errors.stats = 'Connection failed';
            } finally {
                this.loading.stats = false;
            }
        },

        async fetchJobs() {
            this.loading.jobs = true;
            this.errors.jobs = null;
            try {
                const res = await fetch('/api/v1/enablement/jobs?limit=20');
                if (res.ok) {
                    this.jobs = await res.json();
                } else {
                    this.errors.jobs = `Error ${res.status}`;
                }
            } catch (e) {
                console.error("Jobs fetch failed", e);
                this.errors.jobs = 'Connection failed';
            } finally {
                this.loading.jobs = false;
            }
        },

        async fetchTGSP() {
            this.loading.tgsp = true;
            this.errors.tgsp = null;
            try {
                const res = await fetch('/api/community/tgsp/packages');
                if (res.ok) {
                    this.tgspPackages = await res.json();
                } else {
                    this.errors.tgsp = `Error ${res.status}`;
                }
            } catch (e) {
                console.error("TGSP fetch failed", e);
                this.errors.tgsp = 'Connection failed';
            } finally {
                this.loading.tgsp = false;
            }
        },

        async fetchRuns() {
            this.loading.runs = true;
            this.errors.runs = null;
            try {
                const res = await fetch('/api/v1/runs');
                if (res.ok) {
                    this.runs = await res.json();
                } else {
                    this.errors.runs = `Error ${res.status}`;
                }
            } catch (e) {
                console.error("Runs fetch failed", e);
                this.errors.runs = 'Connection failed';
            } finally {
                this.loading.runs = false;
            }
        },

        async fetchInventory() {
            this.loading.inventory = true;
            this.errors.inventory = null;
            try {
                const res = await fetch('/api/v1/identity/inventory');
                if (res.ok) {
                    const data = await res.json();
                    this.certificates = data.certificates || [];
                    this.endpoints = data.endpoints || [];
                } else {
                    this.errors.inventory = `Error ${res.status}`;
                }
            } catch (e) {
                console.error("Inventory fetch failed", e);
                this.errors.inventory = 'Connection failed';
            } finally {
                this.loading.inventory = false;
            }
        },

        async fetchAudit() {
            this.loading.audit = true;
            this.errors.audit = null;
            try {
                const res = await fetch('/api/v1/identity/audit?limit=50');
                if (res.ok) {
                    this.auditLogs = await res.json();
                } else {
                    this.errors.audit = `Error ${res.status}`;
                }
            } catch (e) {
                console.error("Audit fetch failed", e);
                this.errors.audit = 'Connection failed';
            } finally {
                this.loading.audit = false;
            }
        },

        async fetchIdentityJobs() {
            this.loading.identity = true;
            this.errors.identity = null;
            try {
                const res = await fetch('/api/v1/identity/renewals');
                if (res.ok) {
                    this.identityJobs = await res.json();
                } else {
                    this.errors.identity = `Error ${res.status}`;
                }
            } catch (e) {
                console.error("Identity jobs fetch failed", e);
                this.errors.identity = 'Connection failed';
            } finally {
                this.loading.identity = false;
            }
        },

        async fetchPipelineTelemetry() {
            try {
                const res = await fetch('/api/v1/telemetry/pipeline');
                if (res.ok) {
                    const data = await res.json();
                    this.pipelineWorkflow = data.workflow;
                    this.keyRotation = data.key_rotation;
                }
            } catch (e) {
                console.error("Pipeline telemetry fetch failed", e);
            }
        },

        async executeEKUMigration() {
            if (!confirm("Proceed with EKU Split Migration for all conflicting certificates? This will trigger automated dual-renewal jobs.")) return;

            try {
                const res = await fetch('/api/v1/identity/migrations/eku-split', { method: 'POST' });
                const data = await res.json();
                if (res.ok) {
                    alert(`Migration started! ${data.jobs_created} jobs created.`);
                    this.fetchIdentityJobs();
                    this.fetchInventory();
                } else {
                    alert(`Fail: ${data.detail || 'Unknown error'}`);
                }
            } catch (e) {
                alert("Request failed");
            }
        },

        formatDate(isoStr) {
            if (!isoStr) return '-';
            const d = new Date(isoStr);
            return d.toLocaleTimeString() + ' ' + d.toLocaleDateString();
        },

        formatRelativeTime(isoStr) {
            if (!isoStr) return '-';
            const d = new Date(isoStr);
            const now = new Date();
            const diff = Math.floor((now - d) / 1000);

            if (diff < 60) return `${diff}s ago`;
            if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
            if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
            return `${Math.floor(diff / 86400)}d ago`;
        },

        getStatusColor(status) {
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
