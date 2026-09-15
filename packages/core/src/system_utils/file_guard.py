from __future__ import annotations

import os
from pathlib import Path


class FsValidator:
    @staticmethod
    def validate_existing_directory(path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(f'Directory does not exist: {path}')
        if not path.is_dir():
            raise NotADirectoryError(f'Path is not a directory: {path}')
        if not os.access(path, os.X_OK):
            raise PermissionError(f'No execute permission on directory: {path}')

    @staticmethod
    def validate_existing_file(path: Path) -> None:
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f'File does not exist: {resolved}')
        if not resolved.is_file():
            raise ValueError(f'Path is not a regular file: {resolved}')
        if not os.access(resolved, os.R_OK):
            raise PermissionError(f'No read permission on file: {resolved}')

    @staticmethod
    def validate_new_file(path: Path) -> None:
        resolved = path.resolve()
        FsValidator.validate_existing_directory(resolved.parent)
        if resolved.exists():
            raise FileExistsError(f'File already exists: {resolved}')

    @staticmethod
    def validate_executable_file(path: Path) -> None:
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f'Executable does not exist: {resolved}')
        if not resolved.is_file():
            raise ValueError(f'Path is not a regular file: {resolved}')
        if not os.access(resolved, os.R_OK):
            raise PermissionError(f'No read permission on executable: {resolved}')
        if not os.access(resolved, os.X_OK):
            raise PermissionError(f'No execute permission on executable: {resolved}')
