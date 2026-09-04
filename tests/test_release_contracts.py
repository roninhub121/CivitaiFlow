from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
RELEASE = "22.7.1"


def read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8-sig")


class ReleaseContractTests(unittest.TestCase):
    def test_product_release_is_consistent_between_runtime_layers(self):
        python_release = read("scripts/zzzzz_civitaiflow_release.py")
        browser_shell = read("javascript/premium_shell.js")
        self.assertIn(f'CIVITAIFLOW_VERSION = "{RELEASE}"', python_release)
        self.assertIn(f'const RELEASE_VERSION = "{RELEASE}";', browser_shell)

    def test_stale_library_badge_override_is_removed(self):
        library_status = read("javascript/library_status.js")
        self.assertNotIn("v22.5", library_status)
        self.assertNotIn("refreshVersionBadge", library_status)

    def test_premium_shell_has_critical_dimension_guards(self):
        shell = read("javascript/premium_shell.js")
        for contract in (
            ".cf-brand-mark svg",
            ".cf-frame-shell iframe",
            "#cf_browser_column",
            "#cf_browser_stage",
            "enforceCriticalDimensions",
            "min-height: 640px",
        ):
            self.assertIn(contract, shell)

    def test_release_fallback_uses_current_civitai_account_route(self):
        release_module = read("scripts/zzzzz_civitaiflow_release.py")
        self.assertIn('/user/account', release_module)
        self.assertNotIn('/user/settings', release_module)
        self.assertIn(f"CivitaiFlow/{{CIVITAIFLOW_VERSION}}", release_module)

    def test_browser_bridge_discovers_common_forge_ports(self):
        background = read("browser-extension/background.js")
        manifest = json.loads(read("browser-extension/manifest.json"))
        self.assertIn("const FORGE_PORTS = [7860, 7861, 7862, 7863];", background)
        self.assertEqual(manifest["version"], "0.3.0")
        self.assertIn("http://127.0.0.1/*", manifest["host_permissions"])
        self.assertIn("http://localhost/*", manifest["host_permissions"])

    def test_release_script_loads_after_feature_layers_by_filename(self):
        scripts = [
            "zz_civitaiflow_library.py",
            "zzz_civitaiflow_updates.py",
            "zzzz_civitaiflow_lifecycle.py",
            "zzzzz_civitaiflow_release.py",
        ]
        self.assertEqual(scripts, sorted(scripts))

    def test_release_endpoint_is_declared(self):
        release_module = read("scripts/zzzzz_civitaiflow_release.py")
        self.assertRegex(release_module, re.escape('@app.get("/civitaiflow/api/release")'))


if __name__ == "__main__":
    unittest.main()
