"""Disposable API/UI fixture. Never loads installation credentials or real adapters."""
from pathlib import Path
import sys,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.main import create_app
from app.settings import RuntimeSettings
import uvicorn
with tempfile.TemporaryDirectory(prefix='sem-e2e-') as directory:
    path=Path(directory)
    (path/'bootstrap-token').write_text('test-bootstrap-only')
    app=create_app(RuntimeSettings(data_dir=path,start_runtime=False))
    from e2e_sessions import seed_sessions
    seed_sessions(app.state.store)
    app.state.store.journal.redactor.register('private-fixture-secret')
    app.state.store.journal.write('DEBUG','ha','Lecture réussie : 834 W')
    app.state.store.journal.write('ERROR','ocpp:wallbox','MeterValues : timeout ; password=private-fixture-secret')
    uvicorn.run(app,host='127.0.0.1',port=8088,log_level='warning')
