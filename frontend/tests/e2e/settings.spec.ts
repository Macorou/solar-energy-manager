import {test,expect} from '@playwright/test'
import path from 'node:path'

test('grouped settings preserve configuration, handle failed saves and support both themes on phones',async({page})=>{
  const browserErrors:string[]=[];page.on('pageerror',error=>browserErrors.push(error.message))
  const status=await (await page.request.get('/api/v1/setup/status')).json()
  await page.request.post(status.configured?'/api/v1/auth/login':'/api/v1/setup',{data:{token:'test-bootstrap-only',username:'admin',password:'a-secure-test-password'}})
  const fixture=await (await page.request.get('/api/v1/settings')).json()
  const cloud={start_surplus_w:0,start_delay_s:60,import_tolerance_w:0,stop_delay_s:180,min_run_s:300,restart_delay_s:120}
  const base={armed:false,capabilities_verified:false,offline_behavior_verified:false,priority:1,min_power_w:1380,max_power_w:3700,min_current_a:6,max_current_a:16,phases:1,grid_phases:['L1'],voltage:230,allow_insecure_identity:false,ocpp_profile:'auto',connector_id:1,charge_point_id:'wallbox',vehicle_id:'preview-car',gateway_id:'',target:null,solar_target:null,default_soc_target:80,confirmation_timeout_s:300,cloud}
  fixture.devices=[{...base,id:'preview-charger',name:'Wallbox Pulsar Plus',kind:'charger',mode:'planned'},
    {...base,id:'preview-heater',name:'Ariston NUOS',kind:'water_heater',mode:'off_peak_solar',priority:2,min_power_w:700,max_power_w:2570,grid_phases:[],charge_point_id:'',vehicle_id:'',gateway_id:'PREVIEW-ONLY',target:55,solar_target:75}]
  fixture.vehicles=[{id:'preview-car',name:'Peugeot e-208',vin:'',capacity_kwh:50,efficiency:.85}]
  fixture.schedules=[];fixture.off_peak=[]
  fixture.home_assistant={url:'http://homeassistant.test',grid_entity:'sensor.grid_test',solar_entity:'sensor.solar_test',house_entity:'sensor.house_test',price_entity:'sensor.price_test',invert_grid:false,device_power_entities:{'preview-heater':'sensor.heater_test'},phases:Object.fromEntries(['L1','L2','L3'].map(phase=>[phase,{current_entity:'sensor.current_test_'+phase,voltage_entity:'sensor.voltage_test_'+phase,power_entity:'',max_current_a:20}]))}
  expect((await page.request.put('/api/v1/settings',{data:fixture})).ok()).toBeTruthy()
  const stamp=new Date().toISOString(),sample=(value:number)=>({value,quality:'fresh',usable:true,measured_at:stamp,checked_at:stamp})
  const live={simulation:false,at:stamp,running:true,grid:sample(4820),solar:sample(0),house:sample(4820),house_configured:true,price:sample(.1654),effective_price_per_kwh:.1654,phase_control_enabled:true,phases:{L1:{current:sample(19),voltage:sample(230),power:sample(4370),limit_a:20},L2:{current:sample(1.3),voltage:sample(236),power:sample(307),limit_a:20},L3:{current:sample(.6),voltage:sample(239),power:sample(143),limit_a:20}},solar_budget_w:0,off_peak:false,errors:{},
    devices:fixture.devices.map((config:any)=>({config,state:{observed_power:sample(config.kind==='charger'?4140:0),observed_state:config.kind==='charger'?'Charging':'off',connected:true,vehicle_connected:config.kind==='charger',temperature:config.kind==='charger'?null:58,target_temperature:55,fault:null,currents:{L1:sample(18)}},reason:config.kind==='charger'?'Commande manuelle':'Surplus insuffisant',command:null,reservation_w:0,authorization:null})),vehicles:{'preview-car':{soc:62,range_km:176,measured_at:stamp,fresh:true}}}
  await page.route('**/api/v1/state',route=>route.fulfill({json:live}))
  await page.route('**/api/v1/connections/ocpp',route=>route.fulfill({json:{stations:[{station_id:'wallbox',credentials_saved:true,connected:true,last_error:null,firmware:'6.7.43'}]}}))
  await page.goto('/')
  await page.getByRole('button',{name:'Réglages',exact:true}).click()
  await expect(page.getByRole('article',{name:'Wallbox Pulsar Plus'})).toContainText('4,14 kW')
  await expect(page.getByRole('article',{name:'Ariston NUOS'})).toContainText('58 °C')
  const directory=process.env.SEM_SCREENSHOT_DIR||'test-results'
  for(const theme of ['dark','light']){
    if(theme==='light')await page.getByRole('button',{name:'Passer au thème clair'}).click()
    await page.setViewportSize({width:1440,height:1000})
    await page.screenshot({path:path.join(directory,'settings-'+theme+'-desktop.png'),fullPage:true})
    for(const width of [390,320]){
      await page.setViewportSize({width,height:844})
      expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
      expect(await page.locator('.settings-card').evaluateAll(nodes=>nodes.filter(n=>n.scrollWidth>n.clientWidth+1).length)).toBe(0)
    }
    await page.setViewportSize({width:390,height:844})
    await page.screenshot({path:path.join(directory,'settings-'+theme+'-mobile.png'),fullPage:true})
  }
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme','light')
  await page.getByRole('button',{name:'Réglages',exact:true}).click()
  const trigger=page.getByRole('button',{name:'Configurer Compteur réseau'})
  await trigger.click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByLabel('Entité puissance réseau signée').fill('sensor.discarded_test')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await expect(trigger).toBeFocused()
  expect(await (await page.request.get('/api/v1/settings')).json()).toEqual(fixture)
  const sourceTrigger=page.getByRole('button',{name:'Configurer Consommation maison'})
  await sourceTrigger.click()
  await page.getByLabel('Entité consommation totale de la maison (facultatif)').fill('sensor.new_house_test')
  await page.route('**/api/v1/connections/home-assistant',route=>route.fulfill({status:422,json:{detail:'Capteur non valide pour cet essai'}}))
  await page.getByRole('button',{name:'Enregistrer la source'}).click()
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('Capteur non valide')
  await expect(page.getByLabel('Entité consommation totale de la maison (facultatif)')).toHaveValue('sensor.new_house_test')
  await page.unroute('**/api/v1/connections/home-assistant')
  await page.getByRole('button',{name:'Enregistrer la source'}).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  const saved=await (await page.request.get('/api/v1/settings')).json()
  await expect(sourceTrigger).toBeFocused()
  expect(saved).toEqual({...fixture,home_assistant:{...fixture.home_assistant,house_entity:'sensor.new_house_test'}})
  await page.getByRole('tab',{name:'Intégrations'}).click()
  await page.setViewportSize({width:1440,height:1000})
  await page.screenshot({path:path.join(directory,'settings-integrations-light.png'),fullPage:true})
  await page.getByRole('button',{name:'Configurer Serveur OCPP'}).click()
  await expect(page.getByLabel('URL du serveur OCPP')).toHaveValue('ws://127.0.0.1:8088/ocpp/')
  await expect(page.getByLabel('Mot de passe OCPP')).toHaveValue('')
  await page.screenshot({path:path.join(directory,'settings-ocpp-light.png'),fullPage:true})
  await page.getByRole('button',{name:'Fermer la configuration'}).click()
  await page.getByRole('tab',{name:'Équipements'}).click()
  await page.getByRole('button',{name:'Configurer Compteur réseau'}).click()
  await page.setViewportSize({width:390,height:844})
  const dialog=page.getByRole('dialog')
  expect(await dialog.evaluate(n=>n.scrollWidth<=n.clientWidth+1)).toBeTruthy()
  await page.screenshot({path:path.join(directory,'settings-grid-mobile.png'),fullPage:true})
  await page.getByRole('button',{name:'Fermer la configuration'}).click()
  await page.getByRole('button',{name:'Configurer Ariston NUOS'}).click()
  await page.getByLabel('Consigne sur surplus solaire (°C)').fill('70')
  await page.getByRole('button',{name:'Enregistrer l’appareil'}).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  const afterDevice=await (await page.request.get('/api/v1/settings')).json()
  expect(afterDevice).toEqual({...saved,devices:saved.devices.map((device:any)=>device.id==='preview-heater'?{...device,solar_target:70}:device)})
  await page.getByRole('button',{name:'Configurer Peugeot e-208'}).click()
  await page.getByLabel('Capacité utile connue (kWh, facultatif)').fill('45')
  await page.getByRole('button',{name:'Enregistrer le véhicule'}).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  const afterVehicle=await (await page.request.get('/api/v1/settings')).json()
  expect(afterVehicle).toEqual({...afterDevice,vehicles:[{...afterDevice.vehicles[0],capacity_kwh:45}]})
  expect(browserErrors).toEqual([])
})
