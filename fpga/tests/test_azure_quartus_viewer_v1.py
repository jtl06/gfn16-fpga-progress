import importlib.util
from pathlib import Path
import tempfile
import unittest

SOURCE=Path(__file__).parents[1]/'cloud/prepare-quartus-azure-viewer-v1.py'
spec=importlib.util.spec_from_file_location('azure_private_viewer',SOURCE)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class AzureViewerTests(unittest.TestCase):
    def test_private_exact_client_assets_and_no_session_exposure(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);session=root/'session';session.mkdir();assets=root/'assets';assets.mkdir()
            for name in ('core','vendor'):
                (assets/name).mkdir();(assets/name/'fixture.js').write_text('// public static fixture')
            (assets/'not-served.txt').write_text('not part of client')
            (session/'vnc-password.txt').write_text('unit-test-placeholder')
            (session/'Xauthority').write_text('not served')
            module.build(session,assets)
            web=session/'web'
            self.assertEqual({p.name for p in web.iterdir()},{'core','vendor','index.html'})
            for path in web.rglob('*'):
                self.assertEqual(path.stat().st_mode&0o777,0o700 if path.is_dir() else 0o600)
            html=(web/'index.html').read_text()
            self.assertIn('credentials:{password:',html)
            self.assertNotIn('?password=',html)
            self.assertNotIn('console.',html)

    def test_loopback_file_only_no_recording_and_cleanup(self):
        text=SOURCE.read_text()
        for token in ("listen_host='127.0.0.1'","target_host='127.0.0.1'",'file_only=True','timeout=2700,idle_timeout=600'):
            self.assertIn(token,text)
        shell=SOURCE.with_name('start-quartus-display-azure-v2.sh').read_text()
        self.assertIn('-listen 127.0.0.1 -localhost',shell)
        self.assertIn('"$task_session/web/index.html"',shell)
        self.assertNotIn('xdotool',shell)


if __name__=='__main__':unittest.main()
