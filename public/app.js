function app() {
    return {
        activeTab: 'runs',
        stats: {},
        jobs: [],

        init() {
            this.fetchStats();
            this.fetchJobs();

            // Poll every 5s
            setInterval(() => {
                this.fetchStats();
                if (this.activeTab === 'runs') this.fetchJobs();
            }, 5000);
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

        formatDate(isoStr) {
            if (!isoStr) return '-';
            const d = new Date(isoStr);
            return d.toLocaleTimeString() + ' ' + d.toLocaleDateString();
        }
    }
}
