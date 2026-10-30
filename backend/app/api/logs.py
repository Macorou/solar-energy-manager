from typing import Annotated
import sqlite3
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from app.api.auth import require_auth
from app.diagnostics.models import LogLevel, LogPage

router = APIRouter(prefix='/api/v1/logs', dependencies=[Depends(require_auth)])


def filters(level: LogLevel = 'DEBUG', area: Annotated[list[str] | None, Query(max_length=100)] = None,
            search: Annotated[str, Query(max_length=200)] = ''):
    if area and any(len(a) > 80 for a in area):
        raise HTTPException(422, 'Zone trop longue')
    return {'level': level, 'areas': area or (), 'search': search}


def read(request, options, **kwargs):
    try:
        return request.app.state.store.journal.query(**options, **kwargs)
    except sqlite3.Error:
        raise HTTPException(503, 'Journaux temporairement indisponibles') from None


@router.get('', response_model=LogPage)
def logs(request: Request, options=Depends(filters), after: Annotated[int | None, Query(ge=0)] = None,
         before: Annotated[int | None, Query(ge=1)] = None, limit: Annotated[int, Query(ge=1, le=500)] = 500):
    if after is not None and before is not None:
        raise HTTPException(422, 'Choisir avant ou après, pas les deux')
    return read(request, options, after=after, before=before, limit=limit)


@router.get('/export')
def export_logs(request: Request, options=Depends(filters)):
    data = read(request, options, limit=10000)
    lines = ['Solar Energy Manager · Journaux · UTC · filtres appliqués']
    lines += [f'[{r["area"]}] {r["level"]} {r["at"]} {r["message"]}' for r in data['entries']]
    return Response('\n'.join(lines)+'\n', media_type='text/plain; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename="solar-energy-manager-journaux.txt"',
                             'Cache-Control': 'no-store'})
