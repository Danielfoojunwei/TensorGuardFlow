/**
 * Vue Router Configuration
 *
 * Production-grade routing with:
 * - Deep links for all views
 * - Nested routes for sub-tabs
 * - Route guards for authentication
 * - Named routes for programmatic navigation
 */
import { createRouter, createWebHistory } from 'vue-router'

// Lazy-load view components
const CommandCenter = () => import('../components/CommandCenter.vue')
const ModelsWorkbench = () => import('../components/ModelsWorkbench.vue')
const OperationsCenter = () => import('../components/OperationsCenter.vue')
const SecurityCenter = () => import('../components/SecurityCenter.vue')
const GlobalSettings = () => import('../components/GlobalSettings.vue')
const AuthCenter = () => import('../components/AuthCenter.vue')

const routes = [
    {
        path: '/login',
        name: 'login',
        component: AuthCenter,
        meta: { requiresAuth: false, title: 'Login' }
    },
    {
        path: '/',
        redirect: '/dashboard'
    },
    {
        path: '/dashboard',
        name: 'dashboard',
        component: CommandCenter,
        meta: { requiresAuth: true, title: 'Command Center' }
    },
    {
        path: '/models',
        name: 'models',
        redirect: '/models/registry'
    },
    {
        path: '/models/:tab(registry|training|evaluation|skills|lineage)?',
        name: 'models-tab',
        component: ModelsWorkbench,
        props: route => ({ initialTab: route.params.tab || 'registry' }),
        meta: { requiresAuth: true, title: 'Models' }
    },
    {
        path: '/operations',
        name: 'operations',
        redirect: '/operations/fleets'
    },
    {
        path: '/operations/:tab(fleets|monitor|packages|integrations)?',
        name: 'operations-tab',
        component: OperationsCenter,
        props: route => ({ initialTab: route.params.tab || 'fleets' }),
        meta: { requiresAuth: true, title: 'Operations' }
    },
    {
        path: '/security',
        name: 'security',
        redirect: '/security/overview'
    },
    {
        path: '/security/:tab(overview|identity|keys|policy|audit)?',
        name: 'security-tab',
        component: SecurityCenter,
        props: route => ({ initialTab: route.params.tab || 'overview' }),
        meta: { requiresAuth: true, title: 'Security' }
    },
    {
        path: '/settings',
        name: 'settings',
        component: GlobalSettings,
        meta: { requiresAuth: true, title: 'Settings' }
    },
    {
        path: '/:pathMatch(.*)*',
        name: 'not-found',
        redirect: '/dashboard'
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

// Navigation guard for authentication
// Note: We check localStorage directly here to avoid circular dependency with pinia
router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('auth_token')
    const isAuthenticated = !!token

    // Update document title
    if (to.meta.title) {
        document.title = `${to.meta.title} | DYNAMICAL`
    }

    // Check if route requires authentication
    if (to.meta.requiresAuth !== false && !isAuthenticated) {
        // Save intended destination for redirect after login
        const redirectPath = to.fullPath !== '/' ? to.fullPath : null
        if (redirectPath) {
            sessionStorage.setItem('auth_redirect', redirectPath)
        }
        next({ name: 'login' })
    } else if (to.name === 'login' && isAuthenticated) {
        // Already logged in, redirect to dashboard
        next({ name: 'dashboard' })
    } else {
        next()
    }
})

// Handle 401 errors globally by redirecting to login
export function handleUnauthorized() {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    router.push('/login')
}

export default router
