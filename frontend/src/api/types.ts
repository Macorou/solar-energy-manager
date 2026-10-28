import type {components} from './schema'
type Complete<T> = T extends (infer U)[] ? Complete<U>[] : T extends object ? {[K in keyof T]-?: Complete<T[K]>} : T
export type Settings = Complete<components['schemas']['SettingsDocument']>
export type Device = Complete<components['schemas']['DeviceConfig']>
export type Vehicle = Complete<components['schemas']['VehicleConfig']>
export type Program = Complete<components['schemas']['ChargeProgram']>
export type Cloud = Complete<components['schemas']['CloudSettings']>
export interface Sample {value:number|null; measured_at:string|null; checked_at?:string|null; quality:string; usable?:boolean}
export interface Telemetry {soc:number|null;range_km:number|null;measured_at:string|null;fresh:boolean}
export interface LiveDevice {config:Device;state:{observed_power:Sample|null;observed_state:string;connected:boolean;
  temperature:number|null;target_temperature:number|null;fault:string|null};reason:string;
  reservation_w:number;command:{status:string;power_w:number;reason:string}|null;
  authorization:{target_soc:number;expires_at:string|null}|null;
  effective_target?:number|null;target_source?:'grid'|'solar'}
export interface LiveState {simulation:false;at:string|null;running:boolean;grid:Sample|null;solar:Sample|null;
  house?:Sample|null;house_configured?:boolean;
  solar_budget_w:number|null;off_peak:boolean;errors:Record<string,string>;devices:LiveDevice[];vehicles:Record<string,Telemetry>}
export interface EventRow {id:number;at:string;kind:string;device_id:string|null;details:Record<string,string|number>}
