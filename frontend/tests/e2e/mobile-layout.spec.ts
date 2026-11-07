import {test,expect,type Page} from '@playwright/test'
import path from 'node:path'

async function openFixture(page:Page){
  const status=await (await page.request.get('/api/v1/setup/status')).json()
  await page.request.post(status.configured?'/api/v1/auth/login':'/api/v1/setup',{data:{token:'test-bootstrap-only',username:'admin',password:'a-secure-test-password'}})
  const settings=await (await page.request.get('/api/v1/settings')).json()
  const cloud={start_surplus_w:0,start_delay_s:60,import_tolerance_w:0,stop_delay_s:180,min_run_s:300,restart_delay_s:120}
  const base={armed:false,capabilities_verified:false,offline_behavior_verified:false,priority:1,min_power_w:1380,max_power_w:3700,min_current_a:6,max_current_a:16,phases:1,grid_phases:['L1'],voltage:230,allow_insecure_identity:false,ocpp_profile:'auto',connector_id:1,charge_point_id:'wallbox',vehicle_id:'mobile-car',gateway_id:'',target:null,solar_target:null,default_soc_target:100,confirmation_timeout_s:300,cloud}
  settings.devices=[{...base,id:'mobile-charger',name:'Wallbox Pulsar Plus',kind:'charger',mode:'planned'},
    {...base,id:'mobile-heater',name:'Ariston NUOS',kind:'water_heater',mode:'off_peak_solar',priority:2,min_power_w:700,max_power_w:2570,grid_phases:[],charge_point_id:'',vehicle_id:'',gateway_id:'PREVIEW-ONLY',target:55,solar_target:75}]
  settings.vehicles=[{id:'mobile-car',name:'Peugeot e-208',vin:'',capacity_kwh:50,efficiency:.85}]
  settings.schedules=[{id:'mobile-departure',name:'80%',vehicle_id:'mobile-car',weekdays:[0,1,2,3,4],earliest_start:'22:00',deadline:'05:45',target_soc:80,solar_early:true,solar_horizon_hours:24,enabled:true}]
  settings.off_peak=[{start:'22:00',end:'06:00',weekdays:[0,1,2,3,4,5,6]}]
  expect((await page.request.put('/api/v1/settings',{data:settings})).ok()).toBeTruthy()
  const stamp=new Date().toISOString(),sample=(value:number)=>({value,usable:true,quality:'fresh',measured_at:stamp,checked_at:stamp})
  const live={simulation:false,at:stamp,running:true,grid:sample(500),solar:sample(0),house_configured:false,off_peak:false,errors:{},vehicles:{'mobile-car':{soc:82,range_km:176,fresh:false,measured_at:stamp}},devices:settings.devices.map((config:any)=>({config,state:{connected:true,vehicle_connected:true,observed_power:sample(0),observed_state:config.kind==='charger'?'SuspendedEVSE':'off',temperature:57,target_temperature:75,fault:null},effective_target:75,target_source:'solar',reason:'Surplus insuffisant',reservation_w:0,command:null,authorization:null,charging:config.kind==='charger'?{active:false,energy_kwh:13.76,energy_partial:false,cost_eur:1.9,cost_partial:false,solar_percent:0,soc:82,soc_estimated:true,soc_usable:true}:null}))}
  await page.route('**/api/v1/state',route=>route.fulfill({json:live}))
  await page.goto('/')
  await expect(page.getByRole('article',{name:'Wallbox Pulsar Plus'})).toBeVisible()
}

test('phone cards keep artwork separate from usable full-width controls',async({page},testInfo)=>{
  await openFixture(page)
  for(const name of ['Wallbox Pulsar Plus','Ariston NUOS']){
    const alpha=await page.getByRole('article',{name}).locator('.device-art image').evaluate(async node=>{
      const image=new Image();image.src=node.getAttribute('href')!
      await image.decode()
      const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight
      const context=canvas.getContext('2d')!;context.drawImage(image,0,0)
      return [[0,0],[canvas.width-1,0],[0,canvas.height-1],[canvas.width-1,canvas.height-1]].map(([x,y])=>context.getImageData(x,y,1,1).data[3])
    })
    expect(alpha).toEqual([0,0,0,0])
  }
  // The duration: inline and compact on a desktop, on its own row (16 px, 44 px high) on a phone.
  const duration=async()=>page.getByRole('article',{name:'Wallbox Pulsar Plus'}).evaluate(card=>{
    const select=card.querySelector('.manual-hours select') as HTMLSelectElement,label=card.querySelector('.manual-hours>span')!
    const manual=[...card.querySelectorAll('.mode-switch button')].find(n=>n.textContent==='Manuel')!.getBoundingClientRect()
    const box=select.getBoundingClientRect(),style=getComputedStyle(select),context=document.createElement('canvas').getContext('2d')!
    context.font=`${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
    const needed=context.measureText('12 h').width+parseFloat(style.paddingLeft)+parseFloat(style.paddingRight)+16
    return {below:box.top>=manual.bottom-1,font:parseFloat(style.fontSize),height:box.height,fits:box.width>=needed,
      inside:box.right<=card.getBoundingClientRect().right,label:label.getBoundingClientRect().width>1?label.textContent:null}
  })
  // The webkit-mobile project starts as a touch phone, where the phone layout applies from the start.
  if(!testInfo.project.use.isMobile)expect(await duration()).toMatchObject({below:false,fits:true,label:null})
  for(const theme of ['dark','light']){
    if(theme==='light')await page.getByRole('button',{name:'Passer au thème clair'}).click()
    for(const width of [320,375,390,430]){
      await page.setViewportSize({width,height:844})
      expect(await duration()).toMatchObject({below:true,font:16,fits:true,inside:true,label:'Durée'})
      expect((await duration()).height).toBeGreaterThanOrEqual(44)
      for(const name of ['Wallbox Pulsar Plus','Ariston NUOS']){
        const card=page.getByRole('article',{name})
        const art=await card.locator('.device-art').boundingBox(),controls=await card.locator('.mode-switch').boundingBox()
        expect(art&&controls&&art.y+art.height<=controls.y+1).toBeTruthy()
        expect(await card.locator('.mode-switch button').evaluateAll(nodes=>nodes.every(n=>n.getBoundingClientRect().height>=44))).toBeTruthy()
        expect(await card.evaluate(n=>n.scrollWidth<=n.clientWidth+1)).toBeTruthy()
      }
      expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    }
    await page.setViewportSize({width:390,height:844})
    await page.screenshot({path:path.join(process.env.SEM_SCREENSHOT_DIR||'test-results',`mobile-cards-${theme}-${testInfo.project.name}.png`),fullPage:true,animations:'disabled'})
  }
})

test('phone planning time fields fit their cards and remain editable',async({page},testInfo)=>{
  await openFixture(page)
  await page.getByRole('button',{name:'Planning',exact:true}).click()
  for(const theme of ['dark','light']){
    if(theme==='light')await page.getByRole('button',{name:'Passer au thème clair'}).click()
    for(const width of [320,375,390,430]){
      await page.setViewportSize({width,height:844})
      const overflow=await page.locator('.planning-workspace input[type=time]').evaluateAll(nodes=>nodes.filter(n=>{
        const rect=n.getBoundingClientRect(),parent=n.closest('.plan-card')!.getBoundingClientRect()
        return rect.left<parent.left||rect.right>parent.right||rect.width<70
      }).length)
      expect(overflow).toBe(0)
      expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    }
    await page.getByLabel('Début réseau autorisé').fill('22:15')
    await expect(page.getByLabel('Début réseau autorisé')).toHaveValue('22:15')
    await page.getByLabel('Heure de départ 80%').fill('07:30')
    await expect(page.getByLabel('Heure de départ 80%')).toHaveValue('07:30')
    await page.setViewportSize({width:390,height:844})
    await page.screenshot({path:path.join(process.env.SEM_SCREENSHOT_DIR||'test-results',`mobile-planning-${theme}-${testInfo.project.name}.png`),fullPage:true,animations:'disabled'})
  }
})
