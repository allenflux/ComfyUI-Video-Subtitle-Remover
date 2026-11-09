import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from model_paths import (
    DEFAULT_MODELS_DIR,
    MODELS_DIR_ENV,
    model_path,
    models_dir,
    require_model_file,
)


class ModelPathsTest(unittest.TestCase):
    def test_default_models_directory(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(models_dir(), DEFAULT_MODELS_DIR)
            self.assertEqual(
                model_path("big-lama", "fs_manifest.csv"),
                DEFAULT_MODELS_DIR / "big-lama" / "fs_manifest.csv",
            )

    def test_environment_override(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {MODELS_DIR_ENV: directory}, clear=True):
                self.assertEqual(models_dir(), Path(directory))
                self.assertEqual(
                    model_path("sttn-det", "sttn.pth"),
                    Path(directory) / "sttn-det" / "sttn.pth",
                )

    def test_require_model_file_returns_existing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.onnx"
            path.touch()
            self.assertEqual(require_model_file(path, "test weights"), path)

    def test_missing_model_error_has_path_and_configuration_hint(self):
        path = Path("/missing/models/model.onnx")
        with self.assertRaisesRegex(FileNotFoundError, str(path)) as raised:
            require_model_file(path, "test weights")
        self.assertIn(MODELS_DIR_ENV, str(raised.exception))
        self.assertIn(str(DEFAULT_MODELS_DIR), str(raised.exception))


if __name__ == "__main__":
    unittest.main()
