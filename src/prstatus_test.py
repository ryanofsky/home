import aiohttp.web
import asyncio
import shutil
import prstatus
import tempfile
import unittest
import os

from prstatus import call


class TestStringMethods(unittest.TestCase):
    def setUp(self):
        async def handle(request):
            name = request.match_info.get('name', "You")
            return aiohttp.web.Response(text="Hello, {}!".format(name))

        self.app = aiohttp.web.Application()
        self.app.router.add_route("GET", '/', handle)
        self.app.router.add_route("GET", '/{name}', handle)
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _run(self, client_future, start_server=True):
        loop = self.app.loop
        loop.run_until_complete(self.app.startup())
        handler = self.app.make_handler()
        server_future = loop.create_server(handler, port=8080)
        server = loop.run_until_complete(server_future)
        try:
            client = loop.run_until_complete(client_future)
        finally:
            server.close()
            loop.run_until_complete(server.wait_closed())
            loop.run_until_complete(self.app.shutdown())
            loop.run_until_complete(handler.shutdown())
            loop.run_until_complete(self.app.cleanup())

    def _path(self, filename):
        return os.path.join(self.test_dir, filename)

    def _write(self, filename, contents):
        path = self._path(filename)
        self.assertFalse(os.path.exists(filename))
        with open(path, "w") as fp:
            fp.write(contents)

    def _read(self, filename):
        path = self._path(filename)
        with open(path, "r") as fp:
            return fp.read()

    def _listdir(self):
        return sorted(os.listdir(self.test_dir))

    def test_format(self):
        status1 = prstatus.Status()
        status1.state = prstatus.Attribs.NEEDS_WORK
        format = status1.format()
        status2 = prstatus.Status()
        status2.parse(format)
        self.assertEqual(format, status2.format())

    def test_download(self):
        async def go():
            loop = self.app.loop
            async with aiohttp.ClientSession(loop=loop) as session:
                self.assertEqual(
                    await prstatus.download_url(
                        loop,
                        session,
                        'http://localhost:8080/download',
                        self._path("file.txt"),
                        force=False),
                    self._path("file.txt"))

                self.assertEqual(
                    await prstatus.download_url(
                        loop,
                        session,
                        'http://localhost:8080/download0',
                        self._path("file.txt"),
                        force=True),
                    self._path("file.txt.0"))

                self.assertEqual(
                    await prstatus.download_url(
                        loop,
                        session,
                        'http://localhost:8080/download1',
                        self._path("file.txt"),
                        force=True),
                    self._path("file.txt.1"))
                self.assertEqual(
                    await prstatus.download_url(
                        loop,
                        session,
                        'http://localhost:8080/download2',
                        self._path("file.txt.1"),
                        force=False),
                    self._path("file.txt.1"))
            self.assertEqual(await call(loop, self._listdir),
                             ["file.txt", "file.txt.0", "file.txt.1"])
            self.assertEqual(await call(loop, self._read, "file.txt"),
                             "Hello, download!")
            self.assertEqual(await call(loop, self._read, "file.txt.0"),
                             "Hello, download0!")
            self.assertEqual(await call(loop, self._read, "file.txt.1"),
                             "Hello, download1!")

        self._run(go())

    def test_no_download(self):
        async def go():
            loop = self.app.loop
            await call(loop, self._write, "file.txt", "no_download")
            self.assertEqual(
                await prstatus.download_url(
                    loop,
                    None,
                    'http://localhost:8080/download',
                    self._path("file.txt"),
                    force=False),
                self._path("file.txt"))
            self.assertEqual(await call(loop, self._read, "file.txt"),
                             "no_download")
            self.assertEqual(await call(loop, self._listdir), ["file.txt"])

        self._run(go())


if __name__ == '__main__':
    unittest.main()
