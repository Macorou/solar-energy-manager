import {test,expect} from '@playwright/test'
import path from 'node:path'
test('approved flow and planning support live scenarios, persistence and phone layouts',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message))
  await page.request.post('/api/v1/auth/login',{data:{username:'admin',password:'a-secure-test-password'}})
  const settings=await (await page.request.get('/api/v1/settings')).json()
  if(!settings.schedules.length)settings.schedules=[{id:'visual-departure',name:'Départ travail',vehicle_id:settings.vehicles[0].id,weekdays:[0,1,2,3,4],earliest_start:'22:00',deadline:'05:45',target_soc:80,solar_early:true,solar_horizon_hours:24,enabled:true}]
  if(!settings.off_peak.length)settings.off_peak=[{start:'22:00',end:'06:00',weekdays:[0,1,2,3,4,5,6]}]
  expect((await page.request.put('/api/v1/settings',{data:settings})).ok()).toBeTruthy()
  const stamp=new Date().toISOString(),sample=(value:number)=>({value,usable:true,quality:'fresh',measured_at:stamp,checked_at:stamp})
  const live={simulation:false,at:stamp,running:true,grid:sample(2120),solar:sample(4800),house_configured:false,house:null,off_peak:false,errors:{},vehicles:{},devices:settings.devices.map((config:any)=>({config,state:{connected:true,vehicle_connected:true,observed_power:sample(config.kind==='charger'?3700:2570),observed_state:config.kind==='charger'?'Charging':'on',temperature:48,target_temperature:55,fault:null},reason:'Essai visuel',reservation_w:0,command:null,authorization:null}))}
  await page.route('**/api/v1/state',r=>r.fulfill({json:live}))
  await page.goto('/')
  await expect(page.locator('.sidebar nav button')).toHaveCount(6)
  await expect(page.getByRole('button',{name:'Sessions de charge',exact:true})).toBeVisible()
  await expect(page.locator('.energy-track')).toHaveCount(1)
  await expect(page.locator('[data-use]').filter({has:page.locator('svg')})).toHaveCount(3)
  expect(await page.locator('.energy-bracket').allTextContents()).toEqual(['','','','',''])
  const directory=process.env.SEM_SCREENSHOT_DIR||'test-results'
  for(const theme of ['dark','light']){
    if(theme==='light')await page.getByRole('button',{name:'Passer au thème clair'}).click()
    await page.setViewportSize({width:1440,height:1000})
    await page.screenshot({path:path.join(directory,`overview-${theme}.png`),fullPage:true})
    for(const width of [320,390,768,1024]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)}
    await page.getByRole('button',{name:'Planning',exact:true}).click()
    await page.setViewportSize({width:1440,height:1100});await page.screenshot({path:path.join(directory,`planning-${theme}.png`),fullPage:true})
    for(const width of [320,390,768]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)}
    await page.setViewportSize({width:390,height:900});await page.screenshot({path:path.join(directory,`planning-${theme}-mobile.png`),fullPage:true})
    await page.getByRole('button',{name:'Vue d’ensemble',exact:true}).click()
  }
  const charger=live.devices.find((d:any)=>d.config.kind==='charger')!,heater=live.devices.find((d:any)=>d.config.kind==='water_heater')!
  live.grid=sample(4680);live.solar=sample(0)
  charger.state.observed_power=null as any
  heater.state.observed_power={...sample(2570),usable:false,quality:'stale'}
  await expect(page.locator('.energy-track .energy-import')).toHaveText('4,68 kW')
  await expect(page.locator(`[data-use="${charger.config.id}"]`)).toHaveAttribute('aria-label',charger.config.name+' : 3,7 kW')
  await expect(page.locator(`[data-use="${heater.config.id}"]`)).toHaveAttribute('aria-label',heater.config.name+' : 2,57 kW')
  await expect(page.getByRole('article',{name:charger.config.name}).locator('.device-reading strong')).toHaveText('3,7 kW')
  await page.setViewportSize({width:1440,height:1000})
  await page.screenshot({path:path.join(directory,'overview-retained-desktop.png'),fullPage:true,animations:'disabled'})
  await page.setViewportSize({width:390,height:900})
  await page.screenshot({path:path.join(directory,'overview-retained-mobile.png'),fullPage:true,animations:'disabled'})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  live.grid=sample(4120);charger.state.observed_power=sample(2300);heater.state.observed_power=null as any
  await expect(page.locator('.energy-track .energy-import')).toHaveText('4,12 kW')
  await expect(page.locator(`[data-use="${charger.config.id}"]`)).toHaveAttribute('aria-label',charger.config.name+' : 2,3 kW')
  await expect(page.locator(`[data-use="${heater.config.id}"]`)).toHaveAttribute('aria-label',heater.config.name+' : 2,57 kW')
  live.grid=sample(1000);charger.state.observed_power=sample(0)
  await expect(page.locator('.energy-track .energy-import')).toHaveText('1 kW')
  await expect(page.locator(`[data-use="${charger.config.id}"]`)).toHaveCount(0)
  await expect(page.locator(`[data-use="${heater.config.id}"]`)).toHaveCount(1)
  await expect(page.getByRole('article',{name:charger.config.name}).locator('.device-reading strong')).toHaveText('0 W')
  live.grid=sample(950);heater.state.observed_power=sample(0)
  await expect(page.locator('.energy-track .energy-import')).toHaveText('950 W')
  await expect(page.locator(`[data-use="${heater.config.id}"]`)).toHaveCount(0)
  charger.state.observed_power=sample(3700);heater.state.observed_power=sample(2570)
  live.grid=sample(6920);live.solar=sample(0);await page.reload()
  await expect(page.locator('.energy-track .energy-import')).toHaveText('6,92 kW')
  expect(await page.locator('[data-use]').count()).toBe(3)
  live.grid=sample(-1000);live.solar=sample(7920);await page.reload()
  await expect(page.locator('.energy-track .energy-export')).toHaveText('1 kW')
  await page.getByRole('button',{name:'Planning',exact:true}).click()
  if(!settings.schedules.length)await page.getByRole('button',{name:'Créer un programme'}).click()
  const goal=page.getByLabel(/Objectif de charge .* \(%\)/).first();await goal.fill('86')
  await page.getByLabel(/Surplus pour démarrer.*Ariston/).fill('150')
  await page.getByRole('button',{name:'Enregistrer le planning'}).click()
  await expect(page.getByRole('status')).toHaveText('Planning enregistré')
  await page.reload();await page.getByRole('button',{name:'Planning',exact:true}).click()
  await expect(page.getByLabel(/Objectif de charge .* \(%\)/).first()).toHaveValue('86')
  const saved=await (await page.request.get('/api/v1/settings')).json()
  expect(saved.devices.find((d:any)=>d.kind==='water_heater').cloud.start_surplus_w).toBe(150)
  expect(saved.home_assistant).toEqual(settings.home_assistant)
  expect(errors).toEqual([])
})
