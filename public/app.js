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
        currentTime: '',

        // Loading & Error States
        loading: {
            stats: true,
            jobs: true,
            tgsp: true,
            runs: true,
            inventory: true,
            audit: true
        },
        errors: {
            stats: null,
            jobs: null,
            tgsp: null,
            runs: null,
            inventory: null,
            audit: null
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

            // Poll every 10s (reduced for performance)
            setInterval(() => {
                this.fetchStats();
                this.fetchJobs();
                this.fetchTGSP();
                this.fetchRuns();
                this.fetchInventory();
                this.fetchAudit();
            }, 10000);

            // Re-run icons when tab changes
            this.$watch('activeTab', () => {
                setTimeout(() => {
                    lucide.createIcons();
                    this.initCharts();
                }, 100);
            });

            // Initialize charts after first data load
            setTimeout(() => this.initCharts(), 500);
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
                    this.stats = await res.json();
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
            const colors = {
                'completed': 'text-emerald-400',
                'evaluated': 'text-sky-400',
                'running': 'text-amber-400',
                'failed': 'text-red-400',
                'pending': 'text-white/40',
                'registered': 'text-violet-400'
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
                'registered': 'bg-violet-500/20'
            };
            return colors[status?.toLowerCase()] || 'bg-white/10';
        },

        getCertExpiryClass(daysToExpiry) {
            if (daysToExpiry <= 7) return 'text-red-400 bg-red-500/20';
            if (daysToExpiry <= 30) return 'text-amber-400 bg-amber-500/20';
            return 'text-emerald-400 bg-emerald-500/20';
        }
    }
}
