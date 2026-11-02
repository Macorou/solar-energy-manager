from pathlib import Path
import tempfile,sys,json
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.main import create_app
from app.settings import RuntimeSettings
with tempfile.TemporaryDirectory() as directory:
    schema=create_app(RuntimeSettings(data_dir=Path(directory))).openapi()
(root/'backend/openapi.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
