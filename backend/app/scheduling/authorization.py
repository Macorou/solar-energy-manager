from app.domain.schedules import ChargeAuthorization


def select_authorization(vehicle_id, now, occurrences, default_soc_target):
    applicable = [o for o in occurrences if o.vehicle_id==vehicle_id and o.state=='pending'
                  and o.solar_start_at<=now<o.deadline_at]
    if not applicable:
        return ChargeAuthorization(vehicle_id,False,True,default_soc_target,None,'Solaire : objectif habituel')
    deadline = min(o.deadline_at for o in applicable)
    same = [o for o in applicable if o.deadline_at==deadline]
    target = max(o.target_soc for o in same)
    grid = any(now>=o.network_start_at for o in applicable)
    return ChargeAuthorization(vehicle_id,grid,True,target,deadline,
        'Complément autorisé par le planning' if grid else 'Solaire avant le créneau réseau')

