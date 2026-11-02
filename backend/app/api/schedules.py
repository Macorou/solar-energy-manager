from datetime import timedelta
from dataclasses import asdict
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from app.api.auth import require_auth
from app.settings import ChargeProgram, SettingsDocument
from app.domain.measurements import utcnow
from app.scheduling.recurrence import occurrences_for

router=APIRouter(prefix='/api/v1/schedules',dependencies=[Depends(require_auth)])


def save_programs(store, programs:list[ChargeProgram])->None:
    raw=store.load_settings()
    raw['schedules']=[p.model_dump(mode='json') for p in programs]
    try:
        validated=SettingsDocument.model_validate(raw)
    except ValueError:
        raise ValueError('Programme ou véhicule non valide') from None
    store.save_settings(validated.model_dump(mode='json'))


def persist(request, programs):
    try:
        save_programs(request.app.state.store,programs)
    except ValueError as error:
        raise HTTPException(422,str(error)) from None


@router.get('')
def listing(request:Request):
    return request.app.state.store.load_settings()['schedules']


@router.get('/preview')
def preview(request:Request,days:int=Query(8,ge=1,le=31)):
    config=SettingsDocument.model_validate(request.app.state.store.load_settings())
    now=utcnow()
    jobs=[o for p in config.schedules for o in occurrences_for(p,now,now+timedelta(days=days),config.timezone)]
    return [asdict(o) for o in sorted(jobs,key=lambda x:(x.deadline_at,x.program_id))]


@router.put('')
def replace_all(body:list[ChargeProgram],request:Request):
    persist(request,body)
    return {'ok':True}


@router.post('')
def add(body:ChargeProgram,request:Request):
    values=[ChargeProgram.model_validate(p) for p in listing(request)]
    if any(p.id==body.id for p in values):
        raise HTTPException(409,'Identifiant déjà utilisé')
    persist(request,values+[body])
    return {'ok':True}


@router.put('/{program_id}')
def update(program_id:str,body:ChargeProgram,request:Request):
    values=[ChargeProgram.model_validate(p) for p in listing(request)]
    if body.id!=program_id or not any(p.id==program_id for p in values):
        raise HTTPException(404,'Programme introuvable')
    persist(request,[body if p.id==program_id else p for p in values])
    return {'ok':True}


@router.delete('/{program_id}')
def delete(program_id:str,request:Request):
    persist(request,[ChargeProgram.model_validate(p) for p in listing(request) if p['id']!=program_id])
    return {'ok':True}

