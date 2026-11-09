#!/usr/bin/env python3
"""Install the pinned Video Subtitle Remover model snapshot in parallel."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from urllib.request import Request, urlopen


MODEL_REPOSITORY = "allenflux/ComfyUI-Video-Subtitle-Remover-Models"
MODEL_REVISION = "43085ac35785760c61957372444fcb70b11b3338"
MANIFEST_FILENAME = "MANIFEST.sha256"
MANIFEST_SHA256 = "466c398d3abc1de6b30528d12f56b690cd15b03aa138904d012dc9244836c8c0"
EXPECTED_FILE_COUNT = 8
MODELS_DIR_ENV = "VSR_MODELS_DIR"
DEFAULT_MODELS_DIR = Path("/app/ComfyUI/models/video-subtitle-remover-models")
RAW_ROOT = (
    f"https://raw.githubusercontent.com/{MODEL_REPOSITORY}/{MODEL_REVISION}"
)
CHUNK_SIZE = 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class ModelFile:
    sha256: str
    relative_path: PurePosixPath


@dataclass(frozen=True)
class InstallResult:
    relative_path: PurePosixPath
    status: str
    size: int


def default_destination() -> Path:
    configured = os.environ.get(MODELS_DIR_ENV)
    return Path(configured).expanduser() if configured else DEFAULT_MODELS_DIR


def _safe_relative_path(value: str) -> PurePosixPath:
    if not value or "\\" in value:
        raise ValueError(f"Unsafe model path in manifest: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"Unsafe model path in manifest: {value!r}")
    return path


def parse_manifest(contents: bytes) -> list[ModelFile]:
    try:
        lines = contents.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("Model manifest is not valid UTF-8") from error

    files: list[ModelFile] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        digest, separator, relative_path = line.partition("  ")
        if (
            not separator
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"Invalid manifest line {line_number}: {line!r}")
        files.append(ModelFile(digest, _safe_relative_path(relative_path)))

    if len(files) != EXPECTED_FILE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_FILE_COUNT} model files, found {len(files)}"
        )
    if len({file.relative_path for file in files}) != len(files):
        raise ValueError("Model manifest contains duplicate paths")
    return files


def verify_manifest(contents: bytes) -> list[ModelFile]:
    digest = hashlib.sha256(contents).hexdigest()
    if digest != MANIFEST_SHA256:
        raise ValueError(
            f"Manifest checksum mismatch: expected {MANIFEST_SHA256}, got {digest}"
        )
    return parse_manifest(contents)


def _request(url: str) -> Request:
    return Request(url, headers={"User-Agent": "comfyui-vsr-model-installer/1"})


def _read_url(url: str) -> bytes:
    with urlopen(_request(url), timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _destination_path(destination: Path, relative_path: PurePosixPath) -> Path:
    root = destination.resolve()
    candidate = (destination.joinpath(*relative_path.parts)).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Model path escapes destination: {relative_path}")
    return candidate


def _install_file(
    model_file: ModelFile, destination: Path, raw_root: str = RAW_ROOT
) -> InstallResult:
    target = _destination_path(destination, model_file.relative_path)
    if target.is_file() and _sha256_file(target) == model_file.sha256:
        return InstallResult(model_file.relative_path, "verified", target.stat().st_size)

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    digest = hashlib.sha256()
    size = 0
    url = f"{raw_root}/{quote(model_file.relative_path.as_posix(), safe='/')}"
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".part",
            delete=False,
        ) as output:
            temporary_path = Path(output.name)
            with urlopen(_request(url), timeout=REQUEST_TIMEOUT_SECONDS) as response:
                while chunk := response.read(CHUNK_SIZE):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
        actual_digest = digest.hexdigest()
        if actual_digest != model_file.sha256:
            raise ValueError(
                f"Checksum mismatch for {model_file.relative_path}: "
                f"expected {model_file.sha256}, got {actual_digest}"
            )
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return InstallResult(model_file.relative_path, "downloaded", size)


def _write_atomic(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".part",
            delete=False,
        ) as output:
            temporary_path = Path(output.name)
            output.write(contents)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def install_models(destination: Path, workers: int = 8) -> list[InstallResult]:
    if workers < 1:
        raise ValueError("workers must be at least 1")
    destination = destination.expanduser()
    manifest_url = f"{RAW_ROOT}/{MANIFEST_FILENAME}"
    manifest_contents = _read_url(manifest_url)
    model_files = verify_manifest(manifest_contents)

    results: list[InstallResult] = []
    with ThreadPoolExecutor(max_workers=min(workers, len(model_files))) as executor:
        futures = {
            executor.submit(_install_file, model_file, destination): model_file
            for model_file in model_files
        }
        try:
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                print(
                    f"[{result.status}] {result.relative_path} "
                    f"({result.size / 1024 / 1024:.1f} MiB)",
                    flush=True,
                )
        except BaseException:
            for future in futures:
                future.cancel()
            raise

    _write_atomic(destination / MANIFEST_FILENAME, manifest_contents)
    return sorted(results, key=lambda result: result.relative_path.as_posix())


def _positive_integer(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download the pinned Video Subtitle Remover model snapshot in parallel "
            "and verify every file."
        )
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help=(
            f"model directory (default: ${MODELS_DIR_ENV} or {DEFAULT_MODELS_DIR})"
        ),
    )
    parser.add_argument(
        "--workers",
        type=_positive_integer,
        default=8,
        help="parallel downloads (default: 8)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _argument_parser().parse_args(argv)
    destination = arguments.dest or default_destination()
    print(f"Installing model revision {MODEL_REVISION} into {destination}")
    try:
        results = install_models(destination, arguments.workers)
    except Exception as error:
        print(f"Model installation failed: {error}", file=sys.stderr)
        return 1
    downloaded = sum(result.status == "downloaded" for result in results)
    verified = len(results) - downloaded
    print(
        f"Model installation complete: {downloaded} downloaded, "
        f"{verified} already verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
