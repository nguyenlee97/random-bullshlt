from evaluation.routes import _scenario_acceptance


def scenario(expected, revision=4):
    return {'revision': revision, 'expectation': {
        'l1IssueTypes': expected,
        'note': 'minimum contract',
    }}


def incident(issue, revision=4, state='open'):
    return {'issue_type': issue, 'dataset_revision': revision, 'state': state}


def test_scenario_acceptance_matches_minimum_and_reports_additional_signals():
    value = _scenario_acceptance(scenario(['delivery_drop']), {
        'status': 'completed',
        'incidents': [incident('delivery_drop'), incident('pacing_error')],
    })
    assert value['status'] == 'matched'
    assert value['missing_issue_types'] == []
    assert value['additional_issue_types'] == ['pacing_error']


def test_scenario_acceptance_is_revision_scoped_and_never_hides_missing_signal():
    value = _scenario_acceptance(scenario(['ctr_regression']), {
        'status': 'completed',
        'incidents': [incident('ctr_regression', revision=3), incident('ctr_regression', state='resolved')],
    })
    assert value['status'] == 'not_matched'
    assert value['observed_issue_types'] == []
    assert value['missing_issue_types'] == ['ctr_regression']


def test_disabled_or_failed_evaluation_is_not_reported_as_scenario_failure():
    value = _scenario_acceptance(scenario(['ctr_regression']), {'status': 'disabled', 'incidents': []})
    assert value['status'] == 'not_evaluated'
