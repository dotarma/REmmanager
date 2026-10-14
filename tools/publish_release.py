"""Publish manually dispatched builds after tests pass; never overwrite a release."""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def read_version(root: Path = ROOT) -> str:
    version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Expected a numeric major.minor.patch version')
    tree = ast.parse((root / 're_manager/__init__.py').read_text(encoding='utf-8'))
    python_version = next(ast.literal_eval(node.value) for node in tree.body
                          if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == '__version__' for t in node.targets))
    app_version = ET.parse(root / 'winui/REmmanager.csproj').findtext('./PropertyGroup/Version')
    if python_version != version or app_version != version:
        raise ValueError('Version mismatch: pyproject.toml, Python engine and WinUI must agree')
    return version


def next_tag(configuration: str, version: str, existing: list[str]) -> str:
    if configuration not in ('Debug', 'Release') or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid configuration or version')
    prefix = f'{"debug" if configuration == "Debug" else "main"}-{version}-'
    pattern = re.compile(re.escape(prefix) + r'(\d{3,})')
    numbers = [int(match[1]) for tag in existing if (match := pattern.fullmatch(tag))]
    return f'{prefix}{max(numbers, default=0) + 1:03d}'


def gh(*arguments: str) -> str:
    result = subprocess.run(['gh', *arguments], text=True, capture_output=True)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        result.check_returncode()
    return result.stdout.strip()


def publish(configuration: str, directory: Path, repository: str, commit: str,
            root: Path = ROOT) -> str:
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repository) or not re.fullmatch(r'[a-fA-F0-9]{40}', commit):
        raise ValueError('Expected repository owner/name and full source commit SHA')
    version = read_version(root)
    executable = directory.resolve() / 'REmmanager.exe'
    if not executable.is_file() or executable.stat().st_size == 0:
        raise ValueError('Built REmmanager.exe is missing or empty')
    with executable.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    checksum = executable.with_suffix('.sha256')
    checksum.write_text(f'{digest}  {executable.name}\n', encoding='utf-8')
    # Include drafts: a failed asset upload reserves its number for diagnosis.
    tags = gh('api', '--paginate', f'repos/{repository}/tags?per_page=100', '--jq', '.[].name').splitlines()
    drafts_and_releases = gh('api', '--paginate', f'repos/{repository}/releases?per_page=100', '--jq', '.[].tag_name').splitlines()
    tag = next_tag(configuration, version, tags + drafts_and_releases)
    notes = root / 'artifacts/release-notes.md'
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text(
        f'REmmanager {version} — {configuration}, Windows x64.\n\n'
        f'Source commit: `{commit}`\n\n'
        'Download `REmmanager.exe` and run it. Python, .NET and WinUI are bundled.\n'
        + ('Debug build with embedded managed symbols and optimizations disabled.\n' if configuration == 'Debug' else '')
        + f'\nSHA-256: `{digest}`\n', encoding='utf-8')
    options = ['--prerelease'] if configuration == 'Debug' else []
    gh('release', 'create', tag, '--repo', repository, '--target', commit,
       '--title', f'REmmanager {version} ({configuration}) — {tag}',
       '--notes-file', str(notes), '--draft', *options)
    # Publish only after BOTH assets are uploaded; failed uploads leave a draft.
    gh('release', 'upload', tag, str(executable), str(checksum), '--repo', repository)
    gh('release', 'edit', tag, '--repo', repository, '--draft=false',
       f'--latest={"false" if configuration == "Debug" else "true"}', *options)
    url = gh('release', 'view', tag, '--repo', repository, '--json', 'url', '--jq', '.url')
    print(f'Published {tag}: {url}')
    if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write(f'[{tag}]({url}) · {configuration} · Windows x64\n\nSHA-256: `{digest}`\n')
    return tag


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', choices=('Release', 'Debug'), default='Release')
    parser.add_argument('--directory', type=Path, default=ROOT / 'dist')
    parser.add_argument('--check-version', action='store_true')
    args = parser.parse_args()
    if args.check_version:
        print('Version metadata OK:', read_version())
        return
    if os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch':
        parser.error('Publishing is allowed only from a manual workflow_dispatch run')
    if not os.environ.get('GH_TOKEN'):
        parser.error('GH_TOKEN is required')
    publish(args.configuration, args.directory, os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_SHA'])


if __name__ == '__main__':
    main()
