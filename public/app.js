function app() {
    return {
        activeTab: 'dashboard',
        stats: {},
        jobs: [],
        tgspPackages: [],
        currentTime: '',

        init() {
            this.updateTime();
            setInterval(() => this.updateTime(), 1000);

            this.fetchStats();
            this.fetchJobs();
            this.fetchTGSP();

            // Poll every 5s
            setInterval(() => {
                this.fetchStats();
                this.fetchJobs();
                this.fetchTGSP();
            }, 5000);

            // Re-run icons when tab changes
            this.$watch('activeTab', () => {
                setTimeout(() => lucide.createIcons(), 50);
            });
        },

        updateTime() {
            const now = new Date();
            this.currentTime = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        },

        async fetchStats() {
            try {
                const res = await fetch('/api/v1/enablement/stats');
                if (res.ok) {
                    this.stats = await res.json();
                }
            } catch (e) {
                console.error("Stats fetch failed", e);
            }
        },

        async fetchJobs() {
            try {
                const res = await fetch('/api/v1/enablement/jobs?limit=20');
                if (res.ok) {
                    this.jobs = await res.json();
                }
            } catch (e) {
                console.error("Jobs fetch failed", e);
            }
        },

        async fetchTGSP() {
            try {
                const res = await fetch('/api/community/tgsp/packages');
                if (res.ok) {
                    this.tgspPackages = await res.json();
                }
            } catch (e) {
                console.error("TGSP fetch failed", e);
            }
        },

        formatDate(isoStr) {
            if (!isoStr) return '-';
            const d = new Date(isoStr);
            return d.toLocaleTimeString() + ' ' + d.toLocaleDateString();
        }
    }
}
