/**
 * Dashboard Component Unit Tests
 *
 * Tests for the Dashboard component including:
 * - Empty state rendering
 * - Loading state
 * - Stats display
 * - Error handling
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock lucide-vue-next icons
vi.mock('lucide-vue-next', () => ({
    Activity: { template: '<span class="icon-activity">Activity</span>' },
    Database: { template: '<span class="icon-database">Database</span>' },
    Key: { template: '<span class="icon-key">Key</span>' },
    ShieldCheck: { template: '<span class="icon-shield">ShieldCheck</span>' },
    AlertCircle: { template: '<span class="icon-alert">AlertCircle</span>' }
}))

// Mock child components
vi.mock('@/components/dashboard/PipelineGraph.vue', () => ({
    default: { template: '<div class="mock-pipeline-graph">PipelineGraph</div>' }
}))

vi.mock('@/components/analytics/PerformanceDissect.vue', () => ({
    default: { template: '<div class="mock-performance-dissect">PerformanceDissect</div>' }
}))

// Mock fetch
const mockFetch = vi.fn()
global.fetch = mockFetch


describe('Dashboard Component', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        localStorage.clear()
        mockFetch.mockReset()
        vi.useFakeTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
        localStorage.clear()
    })

    it('should render with loading state initially', async () => {
        mockFetch.mockImplementation(() => new Promise(() => {})) // Never resolves

        const Dashboard = (await import('@/components/Dashboard.vue')).default
        const wrapper = mount(Dashboard, {
            global: {
                stubs: {
                    PipelineGraph: true,
                    PerformanceDissect: true
                }
            }
        })

        // Should show loading state (ellipsis values)
        expect(wrapper.text()).toContain('...')
        expect(wrapper.find('.animate-pulse')).toBeDefined()
    })

    it('should display dashboard title', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                fleet_count: 0,
                compliance_level: 4,
                system_health: { status: 'healthy', uptime_percent: 99.9 }
            })
        })

        const Dashboard = (await import('@/components/Dashboard.vue')).default
        const wrapper = mount(Dashboard, {
            global: {
                stubs: {
                    PipelineGraph: true,
                    PerformanceDissect: true
                }
            }
        })

        expect(wrapper.text()).toContain('System Dashboard')
        expect(wrapper.text()).toContain('Real-time Telemetry')
    })

    it('should render empty state (0 fleets)', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                fleet_count: 0,
                compliance_level: 4,
                key_rotations_24h: 0,
                system_health: { status: 'healthy', uptime_percent: 99.9 }
            })
        })

        const Dashboard = (await import('@/components/Dashboard.vue')).default
        const wrapper = mount(Dashboard, {
            global: {
                stubs: {
                    PipelineGraph: true,
                    PerformanceDissect: true
                }
            }
        })

        await flushPromises()

        // Check for 0 fleets in stats
        expect(wrapper.text()).toContain('0')
        expect(wrapper.text()).toContain('Active Fleets')
    })

    it('should display stats when data loads', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                fleet_count: 5,
                compliance_level: 3,
                key_rotations_24h: 12,
                system_health: { status: 'healthy', uptime_percent: 99.5 }
            })
        })

        const Dashboard = (await import('@/components/Dashboard.vue')).default
        const wrapper = mount(Dashboard, {
            global: {
                stubs: {
                    PipelineGraph: true,
                    PerformanceDissect: true
                }
            }
        })

        await flushPromises()

        expect(wrapper.text()).toContain('5')
        expect(wrapper.text()).toContain('Level 3')
        expect(wrapper.text()).toContain('99.5%')
    })

    it('should show error indicator when API fails', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 500
        })

        const Dashboard = (await import('@/components/Dashboard.vue')).default
        const wrapper = mount(Dashboard, {
            global: {
                stubs: {
                    PipelineGraph: true,
                    PerformanceDissect: true
                }
            }
        })

        await flushPromises()

        // Should show cached data message
        expect(wrapper.text()).toContain('cached data')
    })

    it('should include auth token in request when present', async () => {
        const token = 'test_auth_token'
        localStorage.setItem('auth_token', token)

        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                fleet_count: 1,
                compliance_level: 4,
                system_health: { status: 'healthy', uptime_percent: 100 }
            })
        })

        const Dashboard = (await import('@/components/Dashboard.vue')).default
        mount(Dashboard, {
            global: {
                stubs: {
                    PipelineGraph: true,
                    PerformanceDissect: true
                }
            }
        })

        await flushPromises()

        expect(mockFetch).toHaveBeenCalledWith(
            '/api/v1/dashboard/stats',
            expect.objectContaining({
                headers: expect.objectContaining({
                    'Authorization': `Bearer ${token}`
                })
            })
        )
    })

    it('should poll for updates at 30 second intervals', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                fleet_count: 1,
                compliance_level: 4,
                system_health: { status: 'healthy', uptime_percent: 99.9 }
            })
        })

        const Dashboard = (await import('@/components/Dashboard.vue')).default
        mount(Dashboard, {
            global: {
                stubs: {
                    PipelineGraph: true,
                    PerformanceDissect: true
                }
            }
        })

        await flushPromises()
        expect(mockFetch).toHaveBeenCalledTimes(1)

        // Advance time by 30 seconds
        vi.advanceTimersByTime(30000)
        await flushPromises()

        expect(mockFetch).toHaveBeenCalledTimes(2)
    })

    it('should cleanup interval on unmount', async () => {
        mockFetch.mockResolvedValue({
            ok: true,
            json: async () => ({
                fleet_count: 1,
                compliance_level: 4,
                system_health: { status: 'healthy', uptime_percent: 99.9 }
            })
        })

        const Dashboard = (await import('@/components/Dashboard.vue')).default
        const wrapper = mount(Dashboard, {
            global: {
                stubs: {
                    PipelineGraph: true,
                    PerformanceDissect: true
                }
            }
        })

        await flushPromises()
        wrapper.unmount()

        // Advance time - no additional calls should be made
        vi.advanceTimersByTime(60000)
        await flushPromises()

        expect(mockFetch).toHaveBeenCalledTimes(1)
    })
})


describe('Dashboard Stats Grid', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        localStorage.clear()
        mockFetch.mockReset()
    })

    it('should render 4 stat cards', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                fleet_count: 2,
                compliance_level: 4,
                key_rotations_24h: 5,
                system_health: { status: 'healthy', uptime_percent: 99.9 }
            })
        })

        const Dashboard = (await import('@/components/Dashboard.vue')).default
        const wrapper = mount(Dashboard, {
            global: {
                stubs: {
                    PipelineGraph: true,
                    PerformanceDissect: true
                }
            }
        })

        await flushPromises()

        const statLabels = ['System Health', 'Active Fleets', 'Keys Rotated', 'Compliance']
        for (const label of statLabels) {
            expect(wrapper.text()).toContain(label)
        }
    })
})
