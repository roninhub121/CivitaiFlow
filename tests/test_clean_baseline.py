import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "ronin_ui.py"


class FakeOpts:
    def __init__(self):
        self.data = {}
        self.saved = 0
        self.options = {}

    def set(self, key, value):
        self.data[key] = value

    def save(self, _filename):
        self.saved += 1

    def add_option(self, key, info):
        self.options[key] = info


class FakeOptionInfo:
    def __init__(self, default, label, component=None, component_args=None, section=None):
        self.default = default
        self.label = label
        self.component = component
        self.component_args = component_args or {}
        self.section = section


class BaselineHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.opts = FakeOpts()

        requests = types.ModuleType("requests")
        class RequestException(Exception):
            pass
        requests.RequestException = RequestException
        requests.get = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network must be mocked"))
        sys.modules["requests"] = requests

        gradio = types.ModuleType("gradio")
        gradio.Textbox = type("Textbox", (), {})
        gradio.update = lambda **kwargs: {"__gradio_update__": True, **kwargs}
        sys.modules["gradio"] = gradio

        modules_pkg = types.ModuleType("modules")
        modules_pkg.__path__ = []
        scripts_mod = types.ModuleType("modules.scripts")
        paths_mod = types.ModuleType("modules.paths")
        paths_mod.models_path = cls.tmp.name
        shared_mod = types.ModuleType("modules.shared")
        shared_mod.opts = cls.opts
        shared_mod.config_filename = str(pathlib.Path(cls.tmp.name) / "config.json")
        shared_mod.OptionInfo = FakeOptionInfo
        callbacks_mod = types.ModuleType("modules.script_callbacks")
        callbacks_mod.settings_callbacks = []
        callbacks_mod.tab_callbacks = []
        callbacks_mod.on_ui_settings = callbacks_mod.settings_callbacks.append
        callbacks_mod.on_ui_tabs = callbacks_mod.tab_callbacks.append

        modules_pkg.scripts = scripts_mod
        modules_pkg.paths = paths_mod
        modules_pkg.shared = shared_mod
        modules_pkg.script_callbacks = callbacks_mod
        sys.modules["modules"] = modules_pkg
        sys.modules["modules.scripts"] = scripts_mod
        sys.modules["modules.paths"] = paths_mod
        sys.modules["modules.shared"] = shared_mod
        sys.modules["modules.script_callbacks"] = callbacks_mod

        spec = importlib.util.spec_from_file_location("civitai_clean_baseline", SOURCE)
        cls.ui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.ui)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.opts.data.clear()
        self.opts.saved = 0
        self.ui.DOWNLOAD_STATUS.clear()
        self.ui.EXPIRATION_REGISTRY.clear()
        self.ui.PROCESSED_IDS.clear()
        self.ui.FAILED_IDS.clear()
        self.ui.ACTIVE_TASKS = 0
        self.ui.LAST_CLIPBOARD = ""

    def test_module_imports_with_forge_contract_stubs(self):
        self.assertTrue(callable(self.ui.on_ui_tabs))
        self.assertTrue(callable(self.ui.master_tick))
        self.assertTrue(callable(self.ui.save_and_connect_api))

    def test_api_key_is_actually_persisted(self):
        original = self.ui._validate_api_key
        self.ui._validate_api_key = lambda key: (True, "roninhub", None)
        try:
            status, field_update = self.ui.save_and_connect_api("abc123456789")
        finally:
            self.ui._validate_api_key = original

        self.assertEqual(self.opts.data.get("civitai_api_key"), "abc123456789")
        self.assertEqual(self.opts.saved, 1)
        self.assertIn("Connected as roninhub", status)
        self.assertEqual(field_update.get("value"), "")

    def test_refresh_status_reads_persisted_key_instead_of_losing_it(self):
        self.opts.data["civitai_api_key"] = "abc123456789"
        status = self.ui.initial_api_status()
        self.assertIn("API key saved", status)
        self.assertIn("6789", status)
        self.assertNotIn("abc123456789", status)

    def test_model_page_urls_are_recognized(self):
        self.assertEqual(
            self.ui.parse_civitai_urls("https://civitai.com/models/12345"),
            ["12345"],
        )
        self.assertEqual(
            self.ui.parse_civitai_urls("https://civitai.com/models/12345?modelVersionId=67890"),
            ["12345"],
        )

    @unittest.expectedFailure
    def test_download_file_url_must_not_be_misclassified_as_model_id(self):
        # Civitai file links use /api/download/models/<modelVersionId>.
        # The v22.4 regex returns that version ID as though it were a model ID,
        # so the downstream /api/v1/models/<id> lookup is wrong.
        self.assertEqual(
            self.ui.parse_civitai_urls("https://civitai.com/api/download/models/67890"),
            [],
        )

    def test_manual_paste_queues_without_touching_clipboard_when_sniper_off(self):
        original_clip = self.ui.get_windows_clipboard
        original_start = self.ui.start_downloads
        calls = []
        self.ui.get_windows_clipboard = lambda: (_ for _ in ()).throw(AssertionError("clipboard should not be read"))
        self.ui.start_downloads = lambda ids, threads, force=False: calls.append((ids, threads, force)) or len(ids)
        try:
            text_update, _log = self.ui.master_tick(
                "https://civitai.com/models/12345", False, True, 3
            )
        finally:
            self.ui.get_windows_clipboard = original_clip
            self.ui.start_downloads = original_start

        self.assertEqual(calls, [(["12345"], 3, False)])
        self.assertEqual(text_update, "")

    def test_clipboard_is_process_isolated_not_ctypes(self):
        source = SOURCE.read_text(encoding="utf-8-sig")
        self.assertNotIn("import ctypes", source)
        self.assertIn("subprocess.check_output", source)
        self.assertIn("Get-Clipboard", source)

    def test_clean_baseline_has_no_runtime_javascript_patch_stack(self):
        self.assertFalse((ROOT / "javascript").exists())
        self.assertFalse((ROOT / "browser-extension").exists())


if __name__ == "__main__":
    unittest.main()
