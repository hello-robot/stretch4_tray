import tempfile
import unittest
from pathlib import Path
import sys

# Ensure package root is in path
package_root = Path(__file__).parent.parent
sys.path.insert(0, str(package_root))

from stretch4_tray.stretch_tray import get_config_version, is_version_ahead


class TestCalVerComparison(unittest.TestCase):

    def test_missing_or_empty_user_version(self):
        """User config missing or with empty version string should always trigger reset."""
        self.assertTrue(is_version_ahead("2026.07.08", None))
        self.assertTrue(is_version_ahead("2026.07.08", ""))

    def test_equal_versions(self):
        """Equal CalVer versions should NOT trigger reset."""
        self.assertFalse(is_version_ahead("2026.07.08", "2026.07.08"))
        # Normalized PEP 440 vs zero-padded
        self.assertFalse(is_version_ahead("2026.7.8", "2026.07.08"))
        self.assertFalse(is_version_ahead("2026.07.08", "2026.7.8"))

    def test_repo_version_ahead(self):
        """Repo version ahead of user version should trigger reset."""
        # Day increment
        self.assertTrue(is_version_ahead("2026.07.09", "2026.07.08"))
        # Month increment
        self.assertTrue(is_version_ahead("2026.08.01", "2026.07.31"))
        # Year increment
        self.assertTrue(is_version_ahead("2027.01.01", "2026.12.31"))
        # Patch/post increment
        self.assertTrue(is_version_ahead("2026.07.08.1", "2026.07.08"))

    def test_repo_version_behind(self):
        """Repo version behind user version should NOT trigger reset."""
        self.assertFalse(is_version_ahead("2026.07.07", "2026.07.08"))
        self.assertFalse(is_version_ahead("2026.06.30", "2026.07.01"))
        self.assertFalse(is_version_ahead("2025.12.31", "2026.01.01"))

    def test_yaml_files_comparison(self):
        """Test comparing versions extracted from two stub YAML files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            yaml_old = tmp_path / "old_stretch_tray.yaml"
            yaml_new = tmp_path / "new_stretch_tray.yaml"
            yaml_no_ver = tmp_path / "legacy_stretch_tray.yaml"

            yaml_old.write_text("- version: '2026.07.01'\n- key: home\n  name: Home\n")
            yaml_new.write_text("- version: '2026.08.15'\n- key: home\n  name: Home\n")
            yaml_no_ver.write_text("- key: home\n  name: Home\n")

            ver_old = get_config_version(yaml_old)
            ver_new = get_config_version(yaml_new)
            ver_no_ver = get_config_version(yaml_no_ver)

            self.assertEqual(ver_old, "2026.07.01")
            self.assertEqual(ver_new, "2026.08.15")
            self.assertIsNone(ver_no_ver)

            # New config version is ahead of old config version
            self.assertTrue(is_version_ahead(ver_new, ver_old))

            # Old config version is NOT ahead of new config version
            self.assertFalse(is_version_ahead(ver_old, ver_new))

            # New config version is ahead of legacy config with no version
            self.assertTrue(is_version_ahead(ver_new, ver_no_ver))


if __name__ == "__main__":
    unittest.main()
