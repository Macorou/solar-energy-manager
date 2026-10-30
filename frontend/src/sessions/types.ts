import type {components} from '../api/schema'
export type SessionPage=components['schemas']['SessionPage']
export type ChargingSession=components['schemas']['ChargingSession']
export type Totals=components['schemas']['Totals']
export type Bucket=components['schemas']['Bucket']
export type Breakdown=components['schemas']['Breakdown']
export type Option=components['schemas']['Option']
export type Period='month'|'year'|'total'
export type Group='solar'|'charger'|'vehicle'
export type Metric='energy'|'cost'
export type Sort='date'|'charger'|'vehicle'|'energy'|'duration'|'solar'|'cost'
export type Series={id:string;name:string;color:string}
