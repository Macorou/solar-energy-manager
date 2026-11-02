"""Opt in with SEM_TEST_IMAGE=sem:test on a Docker-enabled runner."""
import json,os,subprocess,time,urllib.request,urllib.error,uuid
import pytest
image=os.environ.get('SEM_TEST_IMAGE')
pytestmark=pytest.mark.skipif(not image,reason='Docker smoke test runs in CI with SEM_TEST_IMAGE')


def docker(*args): return subprocess.check_output(['docker',*args],text=True).strip()


def test_image_bootstrap_persistence_and_unprivileged_runtime():
    suffix=uuid.uuid4().hex[:10]
    volume='sem-smoke-'+suffix
    name='sem-smoke-'+suffix
    docker('volume','create',volume)
    def launch():
        docker('run','-d','--name',name,'-p','127.0.0.1::8080','-v',volume+':/data',image)
        port=docker('port',name,'8080/tcp').rsplit(':',1)[-1]
        base='http://127.0.0.1:'+port
        for _ in range(60):
            try:
                with urllib.request.urlopen(base+'/api/v1/health/live',timeout=1) as response:
                    if response.status==200:return base
            except (OSError,urllib.error.URLError): time.sleep(.5)
        raise AssertionError('Container failed to start: '+docker('logs',name))
    try:
        base=launch()
        info=json.loads(docker('inspect',name))[0]
        assert info['Config']['User'] not in ('','0','root')
        assert not info['HostConfig']['Privileged']
        assert all(m['Destination']!='/var/run/docker.sock' for m in info['Mounts'])
        with urllib.request.urlopen(base) as response: assert b'<div id="root"' in response.read()
        token=docker('exec',name,'cat','/data/bootstrap-token')
        key=docker('exec',name,'cat','/data/secrets/master.key')
        request=urllib.request.Request(base+'/api/v1/setup',data=json.dumps({'token':token,'username':'admin',
            'password':'test-only-secure-password'}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response:
            assert response.status==200
            cookie=response.headers['Set-Cookie'].split(';',1)[0]
        log_request=urllib.request.Request(base+'/api/v1/logs',headers={'Cookie':cookie})
        with urllib.request.urlopen(log_request) as response:
            initial_logs=json.load(response)
        assert any(row['area']=='system' for row in initial_logs['entries'])
        first_id=initial_logs['entries'][0]['id']
        docker('stop','--time','15',name)
        assert docker('inspect','--format','{{.State.ExitCode}}',name)=='0'
        docker('rm',name)
        base=launch()
        assert docker('exec',name,'cat','/data/secrets/master.key')==key
        log_request=urllib.request.Request(base+'/api/v1/logs',headers={'Cookie':cookie})
        with urllib.request.urlopen(log_request) as response:
            reopened_logs=json.load(response)
        assert any(row['id']==first_id for row in reopened_logs['entries'])
        assert reopened_logs['cursor']>initial_logs['cursor']
        with urllib.request.urlopen(base+'/api/v1/setup/status') as response:
            assert json.load(response)['configured']
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True)
        subprocess.run(['docker','volume','rm',volume],capture_output=True)
