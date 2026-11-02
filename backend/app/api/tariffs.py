from fastapi import APIRouter,Depends,Request
from app.api.auth import require_auth
from app.settings import OffPeakWindow

router=APIRouter(prefix='/api/v1/tariffs',dependencies=[Depends(require_auth)])


@router.get('/off-peak')
def listing(request:Request):
    return request.app.state.store.load_settings()['off_peak']


@router.put('/off-peak')
def replace_all(body:list[OffPeakWindow],request:Request):
    settings=request.app.state.store.load_settings()
    settings['off_peak']=[w.model_dump(mode='json') for w in body]
    request.app.state.store.save_settings(settings)
    return {'ok':True}
