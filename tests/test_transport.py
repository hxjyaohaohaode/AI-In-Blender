"""Exercise real subprocesses and HTTP against a local fixture server."""
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import base64
from ai_modeling_assistant.core.config import ProviderConfig
from ai_modeling_assistant.core.process import ProcessJob


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = subprocess.Popen([sys.executable, str(Path(__file__).parent / 'fixtures/provider_server.py')],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        cls.port = int(cls.server.stdout.readline())
        cls.base = f'http://127.0.0.1:{cls.port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=5)
        cls.server.stdout.close()

    def config(self, protocol='chat', model='fixture'):
        return ProviderConfig(base_url=self.base, protocol=protocol, model=model,
                              api_key='sensitive-token', options={'poll_interval': 0.1})

    def run_job(self, payload):
        job = ProcessJob(payload)
        try:
            end = time.monotonic() + 10
            while time.monotonic() < end:
                result = job.poll()
                if result is not None:
                    return result
                time.sleep(0.02)
            self.fail('Worker did not finish')
        finally:
            job.cancel()

    def test_chat_through_process(self):
        result = self.run_job({'action': 'chat', 'config': self.config().payload(),
                               'messages': [{'role': 'user', 'content': 'cube'}]})
        self.assertFalse(result['error'])
        self.assertEqual(result['prompt_tokens'], 11)
        self.assertIn('primitive_cube_add', result['content'])

    def test_upstream_errors_do_not_leak_keys(self):
        result = self.run_job({'action': 'chat', 'config': self.config(model='error').payload(),
                               'messages': [{'role': 'user', 'content': 'cube'}]})
        self.assertIn('503', result['error'])
        self.assertNotIn('sensitive-token', str(result))

    def test_cancellation_kills_worker_and_removes_temporary_files(self):
        job = ProcessJob({'action': 'chat', 'config': self.config(model='slow').payload(),
                           'messages': [{'role': 'user', 'content': 'cube'}]})
        directory = job.directory.name
        self.assertIsNone(job.poll())
        job.cancel()
        self.assertIsNotNone(job.process.poll())
        self.assertFalse(Path(directory).exists())
        job.cancel()

    def test_deadline_terminates_worker(self):
        job = ProcessJob({'action': 'chat', 'config': self.config(model='slow').payload(),
                           'messages': [{'role': 'user', 'content': 'cube'}]})
        job.timeout = -1
        self.assertIn('timed out', job.poll()['error'])
        self.assertIsNotNone(job.process.poll())

    def test_native_and_bridge_asset_protocols(self):
        for protocol, capability in [('images', 'image'), ('speech', 'speech'), ('meshy', 'model3d'),
                                      ('bridge', 'world'), ('bridge', 'video')]:
            with self.subTest(protocol=protocol, capability=capability), tempfile.TemporaryDirectory() as folder:
                config = self.config(protocol)
                if protocol == 'speech':
                    config.options['response_format'] = 'wav'
                result = self.run_job({'action': 'generate', 'config': config.payload(),
                    'capability': capability, 'prompt': 'fixture asset', 'output_dir': folder})
                self.assertFalse(result.get('error'), result)
                self.assertTrue(Path(result['artifacts'][0]['path']).is_file())
                self.assertEqual(result['artifacts'][0]['kind'], capability)

    def test_transcription_multipart(self):
        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder) / 'voice.wav'
            audio.write_bytes(b'RIFF fixture audio')
            result = self.run_job({'action': 'generate', 'config': self.config('transcription').payload(),
                'capability': 'transcription', 'prompt': '', 'input_path': str(audio), 'output_dir': folder})
            self.assertFalse(result.get('error'), result)
            self.assertEqual(result['content'], 'Rotate the object slowly')

    def test_vision_sends_binary_image_and_rejects_disabled_capability(self):
        from ai_modeling_assistant.core.attachments import attachment, vision_parts
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'sketch.png'
            path.write_bytes(png)
            ref = attachment(path)
            with self.assertRaises(ValueError):
                vision_parts([ref],enabled=False)
            config = self.config()
            config.options['vision'] = True
            result = self.run_job({'action':'chat','config':config.payload(),
                'messages':[{'role':'user','content':[{'type':'text','text':'Read this sketch'}]+vision_parts([ref],enabled=True)}]})
            self.assertFalse(result.get('error'),result)
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'):
                vision_parts([ref],enabled=True)

    def test_bridge_uploads_actual_conditioning_bytes(self):
        from ai_modeling_assistant.core.attachments import attachment
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'reference.txt'
            path.write_text('Use this exact scene description',encoding='utf-8')
            result = self.run_job({'action':'generate','config':self.config('bridge').payload(),
                'capability':'world','prompt':'scene','output_dir':folder,'inputs':[attachment(path)]})
            self.assertFalse(result.get('error'),result)
            native = self.run_job({'action':'generate','config':self.config('meshy').payload(),
                'capability':'model3d','prompt':'scene','output_dir':folder,'inputs':[attachment(path)]})
            self.assertIn('does not support binary conditioning',native['error'])


if __name__ == '__main__':
    unittest.main()
