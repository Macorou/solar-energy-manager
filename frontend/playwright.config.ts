import {defineConfig,devices} from '@playwright/test'
export default defineConfig({testDir:'tests/e2e',workers:1,timeout:60000,
  projects:[{name:'chromium',use:{browserName:'chromium'}},
    {name:'webkit-mobile',testMatch:['mobile-layout.spec.ts','sessions.spec.ts'],use:{...devices['iPhone 13'],browserName:'webkit',launchOptions:{}}}],
  use:{baseURL:'http://127.0.0.1:8088',headless:true,viewport:{width:1920,height:1080},
    launchOptions:process.env.SEM_BROWSER?{executablePath:process.env.SEM_BROWSER}:{}},
  webServer:{command:`"${process.env.SEM_PYTHON||'python'}" ../scripts/e2e_server.py`,url:'http://127.0.0.1:8088/api/v1/health/live',reuseExistingServer:false,timeout:30000}})

