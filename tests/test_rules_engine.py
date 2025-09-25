"""Tests for the rules engine and official rules implementation (updated severities)."""

import pytest
from data_gatherer.reporting.rules import (
    RulesEngine, RuleRegistry, RuleResult, RuleType, register_official_rules
)
from data_gatherer.reporting.rules.official_rules import (
    MissingCpuRequestRule, MissingMemoryRequestRule,
    MissingCpuLimitRule, MissingMemoryLimitRule,
    ImagePullPolicyAlwaysRule, MissingReadinessProbeRule
)


class TestRuleRegistry:
    def test_register_and_get_rule(self):
        registry = RuleRegistry()
        rule = MissingCpuRequestRule()
        registry.register(rule)
        retrieved = registry.get_rule('missing_cpu_request')
        assert retrieved == rule
        assert retrieved.name == 'missing_cpu_request'

    def test_get_nonexistent_rule_raises_keyerror(self):
        registry = RuleRegistry()
        with pytest.raises(KeyError):
            registry.get_rule('nonexistent_rule')

    def test_unregister_rule(self):
        registry = RuleRegistry()
        rule = MissingCpuRequestRule()
        registry.register(rule)
        assert registry.unregister('missing_cpu_request') is True
        assert registry.unregister('missing_cpu_request') is False
        with pytest.raises(KeyError):
            registry.get_rule('missing_cpu_request')

    def test_enable_disable_rule(self):
        registry = RuleRegistry()
        rule = MissingCpuRequestRule()
        registry.register(rule)
        assert rule.enabled is True
        assert registry.disable_rule('missing_cpu_request') is True
        assert rule.enabled is False
        assert registry.enable_rule('missing_cpu_request') is True
        assert rule.enabled is True
        assert registry.disable_rule('nonexistent') is False
        assert registry.enable_rule('nonexistent') is False


class TestRulesEngine:
    def test_engine_with_empty_registry(self):
        engine = RulesEngine(RuleRegistry())
        context = {
            'cell_value': '',
            'column_name': 'CPU_req_m',
            'row_data': {},
            'report_type': 'capacity'
        }
        result = engine.evaluate_cell(context)
        assert result.rule_type == RuleType.NONE
        assert not result

    def test_engine_with_official_rules(self):
        registry = RuleRegistry()
        register_official_rules(registry)
        engine = RulesEngine(registry)
        context = {
            'cell_value': '',
            'column_name': 'CPU_req_m',
            'row_data': {},
            'report_type': 'capacity'
        }
        result = engine.evaluate_cell(context)
        assert result.rule_type == RuleType.ERROR_MISS
        assert result.css_class == 'error-miss-cell'
        assert 'CPU request' in result.message
        assert result.matched_rule == 'missing_cpu_request'

    def test_engine_priority_error_over_warning(self):
        registry = RuleRegistry()
        register_official_rules(registry)
        engine = RulesEngine(registry)
        context = {
            'cell_value': '',
            'column_name': 'CPU_req_m',
            'row_data': {},
            'report_type': 'capacity'
        }
        result = engine.evaluate_cell(context)
        assert result.rule_type == RuleType.ERROR_MISS


class TestOfficialRules:
    def test_missing_cpu_request_rule(self):
        rule = MissingCpuRequestRule()
        assert rule.applies_to({'column_name': 'CPU_req_m'}) is True
        assert rule.applies_to({'column_name': 'CPU_lim_m'}) is False
        for value in ['', '-', 'N/A', 'None', '0', '0m']:
            result = rule.evaluate({'cell_value': value, 'column_name': 'CPU_req_m'})
            assert result.rule_type == RuleType.ERROR_MISS
            assert 'CPU request' in result.message
        result = rule.evaluate({'cell_value': '500m', 'column_name': 'CPU_req_m'})
        assert result.rule_type == RuleType.NONE

    def test_missing_memory_request_rule(self):
        rule = MissingMemoryRequestRule()
        assert rule.applies_to({'column_name': 'Mem_req_Mi'}) is True
        for value in ['', '-', 'N/A', 'None', '0', '0Mi', '0MiB']:
            result = rule.evaluate({'cell_value': value, 'column_name': 'Mem_req_Mi'})
            assert result.rule_type == RuleType.ERROR_MISS
            assert 'Memory request' in result.message

    def test_missing_cpu_limit_rule(self):
        rule = MissingCpuLimitRule()
        assert rule.applies_to({'column_name': 'CPU_lim_m'}) is True
        result = rule.evaluate({'cell_value': '', 'column_name': 'CPU_lim_m'})
        assert result.rule_type == RuleType.WARNING_MISS
        assert 'CPU limit' in result.message

    def test_missing_memory_limit_rule(self):
        rule = MissingMemoryLimitRule()
        assert rule.applies_to({'column_name': 'Mem_lim_Mi'}) is True
        result = rule.evaluate({'cell_value': '', 'column_name': 'Mem_lim_Mi'})
        assert result.rule_type == RuleType.WARNING_MISS
        assert 'Memory limit' in result.message

    def test_image_pull_policy_always_rule(self):
        rule = ImagePullPolicyAlwaysRule()
        assert rule.applies_to({'column_name': 'Image_Pull_Policy'}) is True
        result = rule.evaluate({'cell_value': 'Always', 'column_name': 'Image_Pull_Policy'})
        assert result.rule_type == RuleType.WARNING_MISCONF
        assert 'ImagePullPolicy set to Always' in result.message
        result = rule.evaluate({'cell_value': 'IfNotPresent', 'column_name': 'Image_Pull_Policy'})
        assert result.rule_type == RuleType.NONE

    def test_missing_readiness_probe_rule(self):
        rule = MissingReadinessProbeRule()
        assert rule.applies_to({'column_name': 'Readiness_Probe'}) is True
        for value in ['', '-', 'N/A', 'None', 'No', 'False', 'Missing', 'Not configured']:
            result = rule.evaluate({'cell_value': value, 'column_name': 'Readiness_Probe'})
            assert result.rule_type == RuleType.ERROR_MISS
            assert 'ReadinessProbe missing' in result.message
        result = rule.evaluate({'cell_value': 'Yes', 'column_name': 'Readiness_Probe'})
        assert result.rule_type == RuleType.NONE


class TestRuleResult:
    def test_rule_result_css_class(self):
        error_result = RuleResult(RuleType.ERROR_MISS)
        assert error_result.css_class == 'error-miss-cell'
        warning_result = RuleResult(RuleType.WARNING_MISS)
        assert warning_result.css_class == 'warning-miss-cell'
        info_result = RuleResult(RuleType.INFO)
        assert info_result.css_class == ''
        none_result = RuleResult(RuleType.NONE)
        assert none_result.css_class == ''

    def test_rule_result_boolean_evaluation(self):
        assert bool(RuleResult(RuleType.ERROR_MISS)) is True
        assert bool(RuleResult(RuleType.WARNING_MISS)) is True
        assert bool(RuleResult(RuleType.INFO)) is True
        assert bool(RuleResult(RuleType.NONE)) is False


class TestRulesEngineIntegration:
    def test_complete_workflow(self):
        registry = RuleRegistry()
        register_official_rules(registry)
        engine = RulesEngine(registry)
        # Scenario 1
        context = {
            'cell_value': '', 'column_name': 'CPU_req_m', 'row_data': {
                'Kind': 'Deployment', 'Namespace': 'default', 'Name': 'test-app'
            }, 'report_type': 'capacity'
        }
        result = engine.evaluate_cell(context)
        assert result.rule_type == RuleType.ERROR_MISS
        assert result.css_class == 'error-miss-cell'
        assert result.matched_rule == 'missing_cpu_request'
        # Scenario 2
        context = {
            'cell_value': 'Always', 'column_name': 'Image_Pull_Policy', 'row_data': {
                'Container': 'web-server'
            }, 'report_type': 'containers'
        }
        result = engine.evaluate_cell(context)
        assert result.rule_type == RuleType.WARNING_MISCONF
        assert result.css_class == 'warning-misconf-cell'
        assert result.matched_rule == 'image_pull_policy_always'
        # Scenario 3
        context = {
            'cell_value': '500m', 'column_name': 'CPU_req_m', 'row_data': {}, 'report_type': 'capacity'
        }
        result = engine.evaluate_cell(context)
        assert result.rule_type == RuleType.NONE
        assert result.css_class == ''
        assert not result

    def test_caching_functionality(self):
        registry = RuleRegistry()
        register_official_rules(registry)
        engine = RulesEngine(registry)
        context = {
            'cell_value': '', 'column_name': 'CPU_req_m', 'row_data': {}, 'report_type': 'capacity'
        }
        r1 = engine.evaluate_cell(context)
        r2 = engine.evaluate_cell(context)
        assert r1.rule_type == r2.rule_type
        assert r1.message == r2.message
        assert r1.matched_rule == r2.matched_rule
        engine.clear_cache()
        r3 = engine.evaluate_cell(context)
        assert r3.rule_type == r1.rule_type
