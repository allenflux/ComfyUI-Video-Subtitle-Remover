import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import install_models


def _fixture_manifest(contents):
    return "".join(
        f"{hashlib.sha256(content).hexdigest()}  models/file-{index}.bin\n"
        for index, content in enumerate(contents)
    ).encode()


class InstallModelsTest(unittest.TestCase):
    def test_default_destination_uses_environment_override(self):
        with patch.dict(os.environ, {install_models.MODELS_DIR_ENV: "/tmp/vsr-models"}):
            self.assertEqual(
                install_models.default_destination(), Path("/tmp/vsr-models")
            )

    def test_manifest_rejects_unsafe_paths(self):
        digest = "0" * 64
        for unsafe_path in ("../outside.bin", "/absolute.bin", "..\\outside.bin"):
            lines = [f"{digest}  safe/file-{index}.bin\n" for index in range(7)]
            lines.append(f"{digest}  {unsafe_path}\n")
            with self.subTest(path=unsafe_path), self.assertRaisesRegex(
                ValueError, "Unsafe model path"
            ):
                install_models.parse_manifest("".join(lines).encode())

    def test_manifest_requires_eight_unique_files(self):
        digest = "0" * 64
        seven = "".join(f"{digest}  file-{index}\n" for index in range(7))
        with self.assertRaisesRegex(ValueError, "Expected 8"):
            install_models.parse_manifest(seven.encode())

        duplicate = "".join(f"{digest}  same-file\n" for _ in range(8))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            install_models.parse_manifest(duplicate.encode())

    def test_parallel_install_verifies_files_and_skips_existing_files(self):
        contents = [f"model-{index}".encode() for index in range(8)]
        manifest = _fixture_manifest(contents)
        manifest_digest = hashlib.sha256(manifest).hexdigest()
        base_url = install_models.RAW_ROOT
        responses = {f"{base_url}/{install_models.MANIFEST_FILENAME}": manifest}
        responses.update(
            {
                f"{base_url}/models/file-{index}.bin": content
                for index, content in enumerate(contents)
            }
        )
        requested_urls = []

        def fake_urlopen(request, timeout):
            requested_urls.append(request.full_url)
            return io.BytesIO(responses[request.full_url])

        with tempfile.TemporaryDirectory() as directory, patch.object(
            install_models, "MANIFEST_SHA256", manifest_digest
        ), patch.object(install_models, "urlopen", side_effect=fake_urlopen):
            destination = Path(directory)
            first = install_models.install_models(destination, workers=4)
            self.assertEqual(
                {result.status for result in first}, {"downloaded"}
            )
            for index, content in enumerate(contents):
                self.assertEqual(
                    (destination / "models" / f"file-{index}.bin").read_bytes(),
                    content,
                )
            self.assertEqual(
                (destination / install_models.MANIFEST_FILENAME).read_bytes(),
                manifest,
            )
            self.assertFalse(list(destination.rglob("*.part")))

            requested_urls.clear()
            second = install_models.install_models(destination, workers=3)
            self.assertEqual({result.status for result in second}, {"verified"})
            self.assertEqual(
                requested_urls,
                [f"{base_url}/{install_models.MANIFEST_FILENAME}"],
            )

    def test_bad_download_does_not_replace_existing_file(self):
        expected = b"expected contents"
        record = install_models.ModelFile(
            hashlib.sha256(expected).hexdigest(),
            install_models.PurePosixPath("model.bin"),
        )

        def fake_urlopen(request, timeout):
            return io.BytesIO(b"corrupt contents")

        with tempfile.TemporaryDirectory() as directory, patch.object(
            install_models, "urlopen", side_effect=fake_urlopen
        ):
            destination = Path(directory)
            target = destination / "model.bin"
            target.write_bytes(b"old contents")
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                install_models._install_file(record, destination)
            self.assertEqual(target.read_bytes(), b"old contents")
            self.assertFalse(list(destination.rglob("*.part")))


if __name__ == "__main__":
    unittest.main()
