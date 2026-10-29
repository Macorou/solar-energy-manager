import {test,expect} from '@playwright/test'
import path from 'node:path'

test('configure locally, plan 80 percent at 05:45, keep real and simulated data separate',async({page})=>{
  await page.setViewportSize({width:1280,height:900})
  await page.goto('/')
  await page.getByLabel('Code de première installation').fill('test-bootstrap-only')
  await page.getByLabel('Mot de passe',{exact:true}).fill('a-secure-test-password')
  await page.getByRole('button',{name:'Créer mon compte'}).click()
  await expect(page.getByRole('heading',{name:'Pilotage énergie'})).toBeVisible()
  await page.getByRole('button',{name:'Voiture',exact:true}).click()
  await page.getByRole('button',{name:'Ajouter un véhicule',exact:true}).click()
  await page.getByLabel('Nom du véhicule').fill('Peugeot e-208 2020')
  await page.getByLabel('Capacité utile connue (kWh, facultatif)').fill('40')
  await expect(page.getByText('Son rendement initial de 85 %', {exact:false})).toBeVisible()
  await page.getByRole('button',{name:'Enregistrer le véhicule'}).click()
  await expect(page.getByRole('status')).toHaveText('Véhicule enregistré')
  await page.getByRole('button',{name:'Ajouter une borne'}).click()
  await page.getByLabel('Identifiant de la borne OCPP').fill('pulsar-maison')
  await page.getByLabel('Phase réseau utilisée').selectOption('L2')
  await page.getByRole('button',{name:'Enregistrer l’appareil'}).click()
  await expect(page.getByRole('status')).toHaveText('Appareil enregistré')
  await page.getByRole('button',{name:'Eau chaude',exact:true}).click()
  await page.getByRole('button',{name:'Ajouter un ballon'}).click()
  await page.getByLabel('Identifiant passerelle Ariston').fill('passerelle-test')
  await expect(page.getByLabel('Consigne sur le réseau (°C)')).toHaveValue('55')
  await expect(page.getByLabel('Consigne sur surplus solaire (°C)')).toHaveValue('55')
  await page.getByLabel('Consigne sur surplus solaire (°C)').fill('70')
  await page.getByRole('button',{name:'Enregistrer l’appareil'}).click()
  await expect(page.getByRole('status')).toHaveText('Appareil enregistré')
  await page.getByRole('button',{name:'Planning',exact:true}).click()
  await page.getByRole('button',{name:'Créer un programme'}).click()
  await page.getByLabel('Nom du programme').fill('Départ travail')
  await page.getByRole('button',{name:'Enregistrer le programme'}).click()
  await expect(page.getByRole('heading',{name:'Départ travail'})).toBeVisible()
  await expect(page.getByText('05:45',{exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Ajouter une plage HC'}).click()
  await page.getByRole('button',{name:'Ajouter une plage HC'}).click()
  await page.getByLabel('Début HC').nth(1).fill('13:00')
  await page.getByLabel('Fin HC').nth(1).fill('14:00')
  await page.getByRole('button',{name:'Enregistrer les heures creuses'}).click()
  await expect(page.getByRole('status')).toHaveText('Heures creuses enregistrées')
  await page.getByRole('button',{name:'Réglages',exact:true}).click()
  await page.getByLabel('Entité consommation totale de la maison (facultatif)').fill('sensor.house_total')
  await page.getByLabel('Entité prix actuel du réseau (€/kWh)').fill('sensor.tariff_test')
  await page.getByLabel('Suivre L2').check()
  await page.getByLabel('Courant réseau L2 (A ou mA)').fill('sensor.phase_2_test')
  await page.getByLabel('Limite L2 (A)').fill('18')
  await page.getByRole('button',{name:'Enregistrer Home Assistant',exact:true}).click()
  await expect(page.getByRole('status')).toHaveText('Connexion HA enregistrée')
  const settings=await (await page.request.get('/api/v1/settings')).json()
  expect(settings.home_assistant.house_entity).toBe('sensor.house_total')
  expect(settings.home_assistant.price_entity).toBe('sensor.tariff_test')
  expect(settings.home_assistant.phases.L2).toMatchObject({current_entity:'sensor.phase_2_test',max_current_a:18})
  expect(settings.devices.find((device:any)=>device.kind==='charger').grid_phases).toEqual(['L2'])
  expect(settings.vehicles[0]).toMatchObject({capacity_kwh:40,efficiency:.85})
  expect(settings.off_peak).toHaveLength(2)
  expect(settings.devices.find((device:any)=>device.kind==='water_heater')).toMatchObject({target:55,solar_target:70})
  expect(settings.schedules[0]).toMatchObject({target_soc:80,deadline:'05:45',weekdays:[0,1,2,3,4]})
  await page.getByRole('button',{name:'Vue d’ensemble',exact:true}).click()
  await expect(page.getByRole('button',{name:'Manuel',exact:true}).first()).toBeDisabled()
  await expect(page.getByRole('button',{name:'Charger maintenant'})).toBeDisabled()
  await expect(page.getByRole('button',{name:'Chauffer maintenant'})).toBeDisabled()
  await expect(page.getByRole('img',{name:'Illustration d’une voiture électrique blanche'})).toBeVisible()
  await expect(page.getByRole('img',{name:'Illustration d’un ballon d’eau chaude'})).toBeVisible()
  for(const name of ['Réseau','Voiture','Eau chaude','Maison'])await expect(page.getByRole('region',{name,exact:true})).toBeVisible()
  await expect(page.getByRole('list',{name:'Plages configurées'}).getByRole('listitem')).toHaveCount(3)
  await page.getByRole('button',{name:'Explorer une simulation'}).click()
  await page.getByRole('button',{name:'Calculer la répartition simulée'}).click()
  await expect(page.getByText('SIMULATION · DONNÉES FICTIVES')).toBeVisible()
  await page.getByRole('button',{name:'Fermer la démonstration'}).click()
  expect(await (await page.request.get('/api/v1/settings')).json()).toEqual(settings)
  const directory=process.env.SEM_SCREENSHOT_DIR||'test-results'
  await page.screenshot({path:path.join(directory,'solar-energy-manager-v0.1.3-desktop.png'),fullPage:true})
  await page.setViewportSize({width:390,height:844})
  await page.screenshot({path:path.join(directory,'solar-energy-manager-v0.1.3-mobile.png'),fullPage:true})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.getByRole('button',{name:'Planning',exact:true}).click()
  await expect(page.getByRole('heading',{name:'Départ travail'})).toBeVisible()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
})

test('creates devices on an insecure HTTP LAN origin without randomUUID',async({page})=>{
  await page.request.post('/api/v1/setup',{data:{token:'test-bootstrap-only',username:'admin',password:'a-secure-test-password'}})
  await page.route('http://192.0.2.1/**',async route=>{
    const url=new URL(route.request().url())
    const headers={...route.request().headers()}
    if(headers.origin)headers.origin='http://127.0.0.1:8088'
    const response=await route.fetch({url:'http://127.0.0.1:8088'+url.pathname+url.search,headers})
    await route.fulfill({response})
  })
  await page.goto('http://192.0.2.1/')
  expect(await page.evaluate(()=>window.isSecureContext)).toBe(false)
  expect(await page.evaluate(()=>typeof crypto.randomUUID)).toBe('undefined')
  await page.getByLabel('Mot de passe',{exact:true}).fill('a-secure-test-password')
  await page.getByRole('button',{name:'Se connecter',exact:true}).click()
  await page.getByRole('button',{name:'Voiture',exact:true}).click()
  await page.getByRole('button',{name:'Ajouter un véhicule',exact:true}).click()
  await page.getByLabel('Nom du véhicule').fill('Véhicule HTTP LAN')
  await page.getByRole('button',{name:'Enregistrer le véhicule'}).click()
  await expect(page.getByRole('status')).toHaveText('Véhicule enregistré')
})

test('reference composition with clearly labelled fictional telemetry remains isolated from the installation',async({page})=>{
  await page.setViewportSize({width:1280,height:800})
  await page.request.post('/api/v1/auth/login',{data:{username:'admin',password:'a-secure-test-password'}})
  const realSettings=await (await page.request.get('/api/v1/settings')).json()
  const fixture=structuredClone(realSettings)
  fixture.home_assistant.house_entity=''
  fixture.schedules[0]={...fixture.schedules[0],earliest_start:'01:30',deadline:'07:00'}
  fixture.off_peak=[{start:'00:45',end:'04:00',weekdays:[0,1,2,3,4,5,6]}]
  const live=await (await page.request.get('/api/v1/state')).json()
  const measured_at=new Date().toISOString()
  const sample=(value:number)=>({value,measured_at,quality:'fresh',usable:true})
  live.grid=sample(4800);live.solar=sample(0)
  live.house_configured=false;live.house=null
  live.devices=live.devices.map((device:any)=>({...device,config:{...device.config,armed:true,mode:device.config.kind==='charger'?'planned':'off_peak_solar'},
    state:{...device.state,connected:true,observed_state:device.config.kind==='charger'?'Charging':'off',observed_power:sample(device.config.kind==='charger'?3700:0),temperature:device.config.kind==='charger'?null:48},
    reason:device.config.kind==='charger'?'Recharge selon le programme':'Chauffe autorisée pendant les heures creuses',
    authorization:device.config.kind==='charger'?{target_soc:80,expires_at:'2026-10-28T06:00:00Z'}:null}))
  live.vehicles=Object.fromEntries(realSettings.vehicles.map((vehicle:any)=>[vehicle.id,{soc:62,range_km:180,measured_at,fresh:true}]))
  await page.route('**/api/v1/state',route=>route.fulfill({json:live}))
  await page.route('**/api/v1/settings',route=>route.fulfill({json:fixture}))
  await page.goto('/')
  await expect(page.getByText('En charge',{exact:true})).toBeVisible()
  await expect(page.getByRole('region',{name:'Maison',exact:true})).toContainText('4,8 kW')
  await page.locator('.header-tag').evaluate(element=>element.textContent='MAQUETTE · DONNÉES FICTIVES')
  const directory=process.env.SEM_SCREENSHOT_DIR||'test-results'
  await page.screenshot({path:path.join(directory,'solar-energy-manager-v0.1.3-reference.png'),fullPage:true})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(1280)
  await page.setViewportSize({width:390,height:844})
  await page.screenshot({path:path.join(directory,'solar-energy-manager-v0.1.3-reference-mobile.png'),fullPage:true})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  for(const width of [320,768,801,980,1024,1440,1920]) {
    await page.setViewportSize({width,height:900})
    const layout=await page.evaluate(()=>({width:document.documentElement.scrollWidth,
      overflowing:[...document.querySelectorAll('.device-card,.mode-switch,.stat-card,.timeline-panel,.connection-card')]
        .filter(element=>element.scrollWidth>element.clientWidth+1).map(element=>element.className)}))
    expect(layout.width,JSON.stringify({viewport:width,...layout})).toBeLessThanOrEqual(width)
    expect(layout.overflowing,JSON.stringify({viewport:width,...layout})).toEqual([])
  }
  // Wider fallback fonts must not let the mobile navigation enlarge its grid.
  await page.setViewportSize({width:320,height:900})
  const fontProbe=await page.addStyleTag({content:':root{font-family:Verdana,sans-serif}'})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
  await fontProbe.evaluate(element=>element.remove())
  await page.unroute('**/api/v1/settings')
  expect(await (await page.request.get('/api/v1/settings')).json()).toEqual(realSettings)
})

test('old known battery and unchanged idle power remain readable on desktop and mobile',async({page})=>{
  await page.request.post('/api/v1/setup',{data:{token:'test-bootstrap-only',username:'admin',password:'a-secure-test-password'}})
  await page.request.post('/api/v1/auth/login',{data:{username:'admin',password:'a-secure-test-password'}})
  const settings=await (await page.request.get('/api/v1/settings')).json()
  const live=await (await page.request.get('/api/v1/state')).json()
  const measured_at='2026-10-26T15:52:17Z',checked_at=new Date().toISOString()
  const sample=(value:number)=>({value,measured_at,checked_at,quality:'fresh',usable:true})
  const vehicle={id:'old-battery-test',name:'Voiture de test',vin:'',capacity_kwh:null,efficiency:.9}
  const config={id:'idle-test',name:'Borne de test',kind:'charger',armed:true,mode:'solar',priority:1,default_soc_target:80,vehicle_id:vehicle.id}
  const tank={...config,id:'tank-test',name:'Ballon de test',kind:'water_heater',target:55,priority:2}
  settings.vehicles=[vehicle];settings.devices=[config,tank];settings.schedules=[]
  live.grid=sample(1000);live.solar=sample(0)
  live.house_configured=false;live.house=null
  live.devices=[config,tank].map(device=>({config:device,
    state:{connected:true,observed_power:sample(0),observed_state:device.kind==='charger'?'Preparing':'off',temperature:48,target_temperature:55,fault:null},
    command:null,reservation_w:0,authorization:null,reason:'Valeur inchangée confirmée par HA'}))
  live.vehicles={[vehicle.id]:{soc:75,range_km:214,measured_at,fresh:false}}
  await page.route('**/api/v1/state',route=>route.fulfill({json:live}))
  await page.route('**/api/v1/settings',route=>route.fulfill({json:settings}))
  await page.goto('/')
  const car=page.getByRole('article',{name:'Borne de test'})
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:900})
    await expect(car.locator('.big-number')).toHaveText('75%')
    await expect(car.getByText('Donnée ancienne',{exact:true})).toBeVisible()
    await expect(car.locator('.measure-date')).toContainText('26/10/2026')
    await expect(car.locator('.measure-date')).toContainText('16:52')
    await expect(car.locator('.device-reading strong')).toHaveText('0 W')
    await expect(page.getByRole('region',{name:'Maison',exact:true})).toContainText('1 kW')
    await expect(car.getByText('En charge',{exact:true})).toHaveCount(0)
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.locator('.header-tag').evaluate(element=>element.textContent='TEST · DONNÉES FICTIVES')
    await page.screenshot({path:path.join(process.env.SEM_SCREENSHOT_DIR||'test-results',`solar-energy-manager-v0.1.4-${width}.png`),fullPage:true})
  }
  live.house_configured=true;live.house=sample(2500)
  await page.reload()
  await expect(page.getByRole('region',{name:'Maison',exact:true})).toContainText('2,5 kW')
  live.house={...sample(2500),usable:false}
  await page.reload()
  await expect(page.getByRole('region',{name:'Maison',exact:true}).locator('strong')).toHaveText('—')
})

test('charge accounting and phase measurements fit desktop and phone with fictional values',async({page})=>{
  await page.request.post('/api/v1/auth/login',{data:{username:'admin',password:'a-secure-test-password'}})
  const settings=await (await page.request.get('/api/v1/settings')).json()
  const live=await (await page.request.get('/api/v1/state')).json()
  const sample=(value:number)=>({value,usable:true,quality:'fresh',measured_at:new Date().toISOString()})
  live.grid=sample(400);live.solar=sample(1800);live.phase_control_enabled=true
  live.phases=Object.fromEntries(['L1','L2','L3'].map(phase=>[phase,{current:sample(8),voltage:sample(230),power:sample(1800),limit_a:20}]))
  live.devices=live.devices.map((device:any)=>device.config.kind==='charger'?{...device,
    config:{...device.config,armed:true,mode:'planned'},reason:'Attente du planning',
    state:{...device.state,connected:true,vehicle_connected:true,observed_state:'SuspendedEVSE',observed_power:sample(0)},
    charging:{active:true,energy_kwh:12.5,cost_eur:1.24,cost_partial:false,solar_percent:60,soc:78,soc_estimated:true,soc_usable:true,effective_price_per_kwh:.08,average_price_per_kwh:.0992}}:device)
  await page.route('**/api/v1/state',route=>route.fulfill({json:live}))
  await page.goto('/')
  await page.locator('.header-tag').evaluate(element=>element.textContent='TEST · DONNÉES FICTIVES')
  for(const width of [1280,390,320]){
    await page.setViewportSize({width,height:960})
    await expect(page.getByRole('region',{name:'Bilan de recharge'})).toContainText('12,5 kWh')
    await expect(page.getByRole('region',{name:'Bilan de recharge'})).toContainText('60 %')
    await expect(page.getByText('Batterie estimée',{exact:true})).toBeVisible()
    await expect(page.getByText(/Voiture : En attente de charge/)).toBeVisible()
    await expect(page.getByRole('region',{name:'Gestion de la charge par phase'})).toBeVisible()
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    await page.screenshot({path:path.join(process.env.SEM_SCREENSHOT_DIR||'test-results',`solar-energy-manager-v0.1.10-charge-${width}.png`),fullPage:true})
  }
  expect(await (await page.request.get('/api/v1/settings')).json()).toEqual(settings)
})

test('an old Peugeot reference needs no manual confirmation on a phone',async({page})=>{
  await page.request.post('/api/v1/auth/login',{data:{username:'admin',password:'a-secure-test-password'}})
  const live=await (await page.request.get('/api/v1/state')).json()
  live.devices=live.devices.map((device:any)=>device.config.kind==='charger'?{...device,
    state:{...device.state,connected:true,vehicle_connected:true,observed_state:'Preparing'},
    charging:{id:'current-reference',active:true,energy_kwh:0,cost_eur:0,cost_partial:false,solar_percent:null,
      soc:75,soc_estimated:true,soc_usable:false,soc_reference_missing:true,effective_price_per_kwh:null}}:device)
  await page.route('**/api/v1/state',route=>route.fulfill({json:live}))
  let confirmations=0
  page.on('request',request=>{if(request.url().endsWith('/soc-reference'))confirmations++})
  await page.setViewportSize({width:390,height:960});await page.goto('/')
  const car=page.getByRole('article').filter({has:page.getByRole('heading',{name:'Voiture électrique'})})
  await expect(car.locator('.big-number')).toHaveText('75%')
  await expect(page.getByLabel('Pourcentage actuel confirmé (%)')).toHaveCount(0)
  await expect(page.getByRole('button',{name:'Confirmer pour cette recharge'})).toHaveCount(0)
  expect(confirmations).toBe(0)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
})
