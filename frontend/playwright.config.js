// @ts-check
import { defineConfig, devices } from '@playwright/test';

/**
 * TensorGuardFlow E2E Test Configuration
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: [
        ['html', { outputFolder: 'playwright-report' }],
        ['junit', { outputFile: 'test-results/e2e-junit.xml' }],
        ['list']
    ],
    use: {
        baseURL: process.env.BASE_URL || 'http://localhost:8000',
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],
    webServer: process.env.CI ? undefined : {
        command: 'cd .. && make dev-backend',
        url: 'http://localhost:8000/health',
        reuseExistingServer: !process.env.CI,
        timeout: 60000,
    },
    timeout: 30000,
});
