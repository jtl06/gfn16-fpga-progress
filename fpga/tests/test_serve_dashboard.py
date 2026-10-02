"""Allowlist/security tests use in-memory HTTP connections; no server is started."""
import importlib.util
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]/'progress/serve_dashboard.py'
spec = importlib.util.spec_from_file_location('serve_dashboard',SOURCE)
dashboard = importlib.util.module_from_spec(spec); spec.loader.exec_module(dashboard)


class FakeConnection:
    def __init__(self, request):
        self.request = io.BytesIO(request)
        self.response = bytearray()

    def makefile(self, *args):
        return self.request

    def sendall(self, data):
        self.response.extend(data)


class DashboardServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for relative, _ in dashboard.ROUTES.values():
            p = self.root/relative; p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(b'allowed content')
        (self.root/'private.txt').write_bytes(b'PRIVATE')

    def request(self, path, method='GET'):
        conn = FakeConnection(f'{method} {path} HTTP/1.0\r\nHost: 127.0.0.1:8767\r\n\r\n'.encode())
        with patch.object(dashboard.DashboardHandler,'log_message'):
            dashboard.DashboardHandler(conn,('127.0.0.1',10000),SimpleNamespace(fpga_root=self.root))
        head, body = bytes(conn.response).split(b'\r\n\r\n',1)
        return int(head.split()[1]),head,body

    def test_allowlisted_routes_and_mime(self):
        for path, (_,mime) in dashboard.ROUTES.items():
            with self.subTest(path=path):
                code,head,body = self.request(path)
                self.assertEqual(code,200); self.assertEqual(body,b'allowed content')
                self.assertIn(('Content-Type: '+mime).encode(),head)
                self.assertIn(b'X-Content-Type-Options: nosniff',head)

    def test_head_has_no_body(self):
        code,head,body = self.request('/results/dashboard/','HEAD')
        self.assertEqual(code,200); self.assertEqual(body,b'')
        self.assertIn(b'Content-Length: 15',head)

    def test_other_paths_traversal_and_listing_refused(self):
        for path in ['/', '/results/', '/results/dashboard', '/private.txt',
                     '/results/dashboard/../../private.txt', '/results/dashboard/%2e%2e/%2e%2e/private.txt',
                     '/results/dashboard/%252e%252e/private.txt', '/results/dashboard/../dashboard/index.html',
                     '/results/dashboard/snapshot.json/extra', '/results/dashboard/host-observations.json',
                     '/rtl/kernel/example.sv', '/docs/briefs/replies/report.json',
                     'http://evil.example/results/dashboard/']:
            with self.subTest(path=path):
                code,_,body = self.request(path)
                self.assertEqual(code,404); self.assertNotIn(b'PRIVATE',body)

    def test_query_does_not_expand_scope(self):
        self.assertEqual(self.request('/results/dashboard/?file=../../private.txt')[0],200)

    def test_leaf_symlink_refused(self):
        leaf = self.root/'results/dashboard/index.html'
        leaf.unlink(); leaf.symlink_to(self.root/'private.txt')
        self.assertEqual(self.request('/results/dashboard/')[0],404)

    def test_parent_symlink_refused(self):
        directory = self.root/'results/dashboard'
        moved = self.root/'moved-dashboard'; directory.rename(moved); directory.symlink_to(moved,target_is_directory=True)
        self.assertEqual(self.request('/results/dashboard/')[0],404)

    def test_missing_file_and_directory_refused(self):
        leaf = self.root/'results/dashboard/index.html'; leaf.unlink()
        self.assertEqual(self.request('/results/dashboard/')[0],404)
        leaf.mkdir()
        self.assertEqual(self.request('/results/dashboard/')[0],404)

    def test_upload_methods_not_supported(self):
        for method in ('POST','PUT','DELETE','PATCH'):
            self.assertEqual(self.request('/results/dashboard/',method)[0],501)
        self.assertEqual((self.root/'results/dashboard/index.html').read_bytes(),b'allowed content')

    def test_bind_is_fixed_loopback(self):
        with patch.object(dashboard,'HTTPServer') as server:
            dashboard.make_server()
            server.assert_called_once_with(('127.0.0.1',8767),dashboard.DashboardHandler)


if __name__ == '__main__': unittest.main()
