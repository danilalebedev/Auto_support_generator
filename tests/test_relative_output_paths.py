from pathlib import Path

from si_generator.graph.nodes.packaging import _relative_path, _relative_paths


def test_relative_cli_output_paths_become_relative_to_the_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = Path('output/runs/example')
    paths = {'output_root': str(root), 'support_docx': str(root / 'docx/support.docx')}
    assert _relative_paths(root, paths) == {'output_root': '.', 'support_docx': str(Path('docx/support.docx'))}
    assert _relative_path(root, str(root / 'input/template.docx')) == str(Path('input/template.docx'))


def test_already_relative_and_external_paths_are_preserved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / 'output/runs/example'
    assert _relative_path(root, 'input/template.docx') == str(Path('input/template.docx'))
    outside = tmp_path / 'external.docx'
    assert _relative_path(root, str(outside)) == str(outside)
