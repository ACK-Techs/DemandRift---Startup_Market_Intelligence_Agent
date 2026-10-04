"""Thirty real idea inputs exercise privacy/provenance and prompt preparation.

This is input-boundary coverage, not the blocked live model classification score.
The expected answers are never fed to the provider prompt.
"""
import json
from pathlib import Path
import os
import pytest
from app.phase1_prompts import build_phase1_prompt
from test_phase1_prompts import brief

CASES=json.loads(((Path(os.environ['DEMANDRIFT_SCENARIO_ROOT']) if 'DEMANDRIFT_SCENARIO_ROOT' in os.environ else Path(__file__).resolve().parents[3])/'faz-1-fikir-ve-arastirma/tests/fikir-senaryolari.json').read_text())['cases']

@pytest.mark.parametrize('case',CASES,ids=lambda row:row['case_id'])
def test_phase1_recorded_input_remains_human_unconfirmed_data(case):
    selected=brief(case['input'])
    prompt=build_phase1_prompt('brief',selected)
    parsed=json.loads(prompt.input_text)
    assert parsed['brief']['original_idea']==case['input']
    assert parsed['brief']['category_confirmed'] is False
    assert parsed['brief']['market_scope']['value'] is None
    assert parsed['brief']['target_user']['confirmed'] is False
    assert parsed['brief']['problem_or_job']['confirmed'] is False
    assert 'expected' not in parsed and 'case_id' not in parsed
    for identity in (selected.user_id,selected.project_id,selected.research_id):
        assert str(identity) not in prompt.input_text
    assert selected.status=='awaiting_user'
