from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from app.api.auth import require_auth
from app.sessions.models import SessionQuery, SessionPage, ChargingSession, SessionEdit, SessionDelete
from app.sessions.service import SessionService
from app.sessions.export import csv_export, xlsx_export
from app.storage.charging_sessions import SessionHistory

router=APIRouter(prefix='/api/v1/charging-sessions',tags=['Charging sessions'],dependencies=[Depends(require_auth)])


@router.get('',response_model=SessionPage)
def sessions(request:Request, query:Annotated[SessionQuery,Query()]):
    return SessionService(request.app.state.store,query).result()


@router.get('/export')
def export(request:Request, query:Annotated[SessionQuery,Depends()], format:Literal['csv','xlsx']='csv'):
    service=SessionService(request.app.state.store,query)
    rows=service.selection()
    filename=f'sessions-{query.period}-{service.year}-{service.month:02}.{format}'
    headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'}
    if format=='csv':return StreamingResponse(csv_export(rows),media_type='text/csv; charset=utf-8',headers=headers)
    return Response(xlsx_export(rows),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers=headers)


def lookup(store, session_id, db):
    row=db.execute('SELECT * FROM charging_history WHERE id=? AND deleted=0',(session_id,)).fetchone()
    if not row:raise HTTPException(404,'Session introuvable')
    config=store.load_settings()
    return SessionHistory.decode(row,{v['id']:v['name'] for v in config.get('vehicles',[])})


@router.get('/{session_id}',response_model=ChargingSession)
def detail(session_id:str,request:Request):
    store=request.app.state.store
    with store.connection() as db:return lookup(store,session_id,db)


@router.patch('/{session_id}',response_model=ChargingSession)
def edit(session_id:str,body:SessionEdit,request:Request):
    store=request.app.state.store
    config=store.load_settings()
    if body.vehicle_id and not any(v['id']==body.vehicle_id for v in config['vehicles']):
        raise HTTPException(422,'Véhicule inconnu')
    with store.connection() as db:
        row=lookup(store,session_id,db)
        if not row['editable']:raise HTTPException(409,'Seules les sessions locales terminées sont modifiables')
        db.execute('UPDATE charging_history SET vehicle_override=? WHERE id=?',(body.vehicle_id,session_id))
        return lookup(store,session_id,db)


@router.delete('/{session_id}')
def delete(session_id:str,body:SessionDelete,request:Request):
    store=request.app.state.store
    with store.connection() as db:
        row=lookup(store,session_id,db)
        if not row['editable']:raise HTTPException(409,'Seules les sessions locales terminées sont supprimables')
        db.execute('UPDATE charging_history SET deleted=1 WHERE id=?',(session_id,))
    return {'ok':True}
