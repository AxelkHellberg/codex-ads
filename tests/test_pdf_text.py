import json
from pathlib import Path
import shutil
import subprocess

import pytest
from reportlab.platypus import Paragraph as RealParagraph

import codex_ads.reporting as reporting


def summary(text):
    return {'business_type': text, 'goal': text, 'score': text, 'grade': text, 'platforms': [{
        'label': text, 'score': text, 'grade': text,
        'findings': [{'id': text, 'severity': text, 'title': text, 'recommendation': text}],
    }]}


@pytest.mark.parametrize('text', ['Retail </b> & growth <img src="missing.png"/>', '<b>literal</b>', 'A & B < C > D'])
def test_all_summary_fields_are_literal_pdf_text(tmp_path, monkeypatch, text):
    seen = []
    def paragraph(markup, style):
        result = RealParagraph(markup, style)
        seen.append(result.getPlainText())
        return result
    monkeypatch.setattr(reporting, 'Paragraph', paragraph)
    source = tmp_path / 'summary.json'
    source.write_text(json.dumps(summary(text)))
    output = reporting.build_pdf_report(source, tmp_path / 'out')
    assert output.read_bytes().startswith(b'%PDF-')
    assert seen == ['Codex Ads Report', f'Business type: {text}', f'Goal: {text}',
        f'Health score: {text} ({text})', text, f'Score: {text} ({text})',
        f'{text} [{text}] {text}: {text}']


@pytest.mark.skipif(shutil.which('pdftotext') is None, reason='pdftotext is required')
def test_generated_pdf_retains_literal_markup(tmp_path):
    source = tmp_path / 'summary.json'
    source.write_text(json.dumps({'goal': 'Keep <b>literal</b> & A < B'}))
    output = reporting.build_pdf_report(source, tmp_path)
    result = subprocess.run(['pdftotext', str(output), '-'], capture_output=True, text=True, check=True, timeout=10)
    assert 'Keep <b>literal</b> & A < B' in result.stdout
