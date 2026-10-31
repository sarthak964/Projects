import pytest

from app.services import verification_nodes as nodes
from app.services.verification_state import VerificationOutput
from tests.helpers import Inspection


def state(rows, photos=None):
    return {'checklist': [r['item'] for r in rows], 'verification_result': rows, 'photos': photos or []}


def row(name, passed=True, addressed=True, photo_check='no_photo'):
    return {'item': name, 'passed': passed, 'addressed': addressed, 'photo_check': photo_check, 'reasoning': 'Test result'}


def test_perfect_score_is_explicitly_a_notes_only_assessment():
    result = nodes.summarize_node(state([row('Walls'), row('Taps')]))
    assert result['check_score'] == 100
    assert 'Notes-only assessment' in result['summary']
    assert 'Photos were not assessed' in result['summary']
    assert 'not a property certification' in result['summary']
    assert 'Reported as meeting' in result['summary']
    assert '100.0/100' in result['summary']
    nodes.llm.invoke.assert_not_called()


def test_failed_and_missing_items_are_separate_from_reported_passes():
    result = nodes.summarize_node(state([row('Walls'), row('Taps', False), row('Windows', False, False)]))
    assert result['check_score'] == 33.3
    assert 'Reported as meeting the checklist requirement: Walls.' in result['summary']
    assert 'Reported as not meeting the checklist requirement: Taps.' in result['summary']
    assert 'Not sufficiently addressed in the notes: Windows.' in result['summary']


def test_incomplete_score_does_not_claim_every_item_failed():
    result = nodes.flag_incomplete_node(state([row('Walls'), row('Taps', False, False)]))
    assert result['check_score'] == 0
    assert 'add a specific note' in result['summary']
    assert 'not a finding that every item failed' in result['summary']
    assert 'Photos were not assessed' in result['summary']
    nodes.llm.invoke.assert_not_called()


def test_supplied_images_are_not_claimed_to_prove_authenticity():
    result = nodes.summarize_node(state([row('Walls')], photos=[{'checklist_item': 'Walls'}]))
    assert 'supplied images only' in result['summary']
    assert 'no on-site inspection or photo authenticity verification' in result['summary']
    assert 'Photos were not assessed' not in result['summary']


def test_photo_mismatch_requests_correction_without_accusations():
    result = nodes.flag_incomplete_node(state([row('Walls', photo_check='irrelevant')], photos=[{}]))
    assert 'clearer relevant photo or explain the mismatch' in result['summary']
    assert 'photo check result: irrelevant' in result['summary']


@pytest.mark.parametrize('node', [nodes.summarize_node, nodes.flag_incomplete_node])
def test_summary_nodes_still_reject_missing_results(node):
    with pytest.raises(nodes.InvalidVerificationResult):
        node({'checklist': ['Walls'], 'verification_result': [], 'photos': []})


def test_notes_prompt_and_schema_do_not_claim_independent_verification():
    nodes.structured_llm.invoke.side_effect = None
    nodes.structured_llm.invoke.return_value = VerificationOutput(results=[row('Walls') | {'confidence': .9}])
    nodes.check_checklist_node({'checklist': ['Walls'], 'notes': 'Walls are intact', 'photos': []})
    prompt = nodes.structured_llm.invoke.call_args.args[0]
    assert 'not independently verified facts' in prompt
    assert 'reported outcome, not independent verification' in prompt


@pytest.mark.parametrize('addressed', [True, False])
def test_actual_graph_saves_scoped_summary_for_complete_and_incomplete_report(client, headers, store, monkeypatch, addressed):
    inspection = Inspection(client, headers, store, monkeypatch)
    inspection.create()
    inspection.accept()
    inspection.visit()
    for item in ['AC working', 'Fire extinguisher']:
        inspection.upload(item)
    inspection.submit()
    report = inspection.verify(addressed=addressed)
    summary = report['ai_generated_summary']
    assert 'Notes-only assessment' in summary
    assert 'Photos were not assessed' in summary
    saved = inspection.call('GET', f'/reports/{inspection.report_id}', uid=4)
    assert saved['ai_generated_summary'] == summary
    assert report['check_score'] == (50 if addressed else 0)
    nodes.llm.invoke.assert_not_called()
