"""Tests for the rules engine and official rules implementation."""

import pytest
from data_gatherer.reporting.rules import (
    RulesEngine, RuleRegistry, RuleResult, RuleType,
    register_official_rules
)
from data_gatherer.reporting.rules.official_rules import (
    MissingCpuRequestRule, MissingMemoryRequestRule,
    MissingCpuLimitRule, MissingMemoryLimitRule,
    ImagePullPolicyAlwaysRule, MissingReadinessProbeRule
)


class TestRuleRegistry:
    """Test the rule registry functionality."""
    
    def test_register_and_get_rule(self):
        """Test registering and retrieving rules."""
        registry = RuleRegistry()
        rule = MissingCpuRequestRule()
        
        registry.register(rule)
        retrieved = registry.get_rule('missing_cpu_request')
        
        assert retrieved == rule
        assert retrieved.name == 'missing_cpu_request'
    
    def test_get_nonexistent_rule_raises_keyerror(self):
        """Test that getting a non-existent rule raises KeyError."""
        registry = RuleRegistry()
        
        with pytest.raises(KeyError):
            registry.get_rule('nonexistent_rule')
    
    def test_unregister_rule(self):
        """Test unregistering rules."""
        registry = RuleRegistry()
        rule = MissingCpuRequestRule()
        
        registry.register(rule)
        assert registry.unregister('missing_cpu_request') is True
        assert registry.unregister('missing_cpu_request') is False
        
        with pytest.raises(KeyError):
            registry.get_rule('missing_cpu_request')
    
    def test_enable_disable_rule(self):
        """Test enabling and disabling rules."""
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
    """Test the rules engine functionality."""
    
    def test_engine_with_empty_registry(self):
        """Test engine with no rules returns NONE."""
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
        """Test engine with official rules registered."""
        registry = RuleRegistry()
        register_official_rules(registry)
        engine = RulesEngine(registry)
        
        # Test missing CPU request (should be ERROR)
        context = {
            'cell_value': '',
            'column_name': 'CPU_req_m',
            'row_data': {},
            'report_type': 'capacity'
        }
        
        result = engine.evaluate_cell(context)
        assert result.rule_type == RuleType.ERROR
        assert result.css_class == 'error-cell'
        assert 'CPU request' in result.message
        assert result.matched_rule == 'missing_cpu_request'
    
    def test_engine_priority_error_over_warning(self):
        """Test that ERROR rules take priority over WARNING rules."""
        registry = RuleRegistry()
        register_official_rules(registry)
        engine = RulesEngine(registry)
        
        # For a missing CPU value, both request (ERROR) and limit (WARNING) rules could apply
        # But ERROR should take priority
        context = {
            'cell_value': '',
            'column_name': 'CPU_req_m',  # This will trigger ERROR
            'row_data': {},
            'report_type': 'capacity'
        }
        
        result = engine.evaluate_cell(context)
        assert result.rule_type == RuleType.ERROR


class TestOfficialRules:
    """Test the official rules implementation."""
    
    def test_missing_cpu_request_rule(self):
        """Test MissingCpuRequestRule."""
        rule = MissingCpuRequestRule()
        
        # Should apply to CPU request columns
        assert rule.applies_to({
            'column_name': 'CPU_req_m'
        }) is True
        
        assert rule.applies_to({
            'column_name': 'CPU_lim_m'
        }) is False
        
        # Should trigger ERROR for missing values
        missing_values = ['', '-', 'N/A', 'None', '0', '0m']
        for value in missing_values:
            result = rule.evaluate({
                'cell_value': value,
                'column_name': 'CPU_req_m'
            })
            assert result.rule_type == RuleType.ERROR
            assert 'CPU request' in result.message
        
        # Should not trigger for valid values
        result = rule.evaluate({
            'cell_value': '500m',
            'column_name': 'CPU_req_m'
        })
        assert result.rule_type == RuleType.NONE
    
    def test_missing_memory_request_rule(self):
        """Test MissingMemoryRequestRule."""
        rule = MissingMemoryRequestRule()
        
        # Should apply to Memory request columns
        assert rule.applies_to({
            'column_name': 'Mem_req_Mi'
        }) is True
        
        # Should trigger ERROR for missing values
        missing_values = ['', '-', 'N/A', 'None', '0', '0Mi', '0MiB']
        for value in missing_values:
            result = rule.evaluate({
                'cell_value': value,
                'column_name': 'Mem_req_Mi'
            })
            assert result.rule_type == RuleType.ERROR
            assert 'Memory request' in result.message
    
    def test_missing_cpu_limit_rule(self):
        """Test MissingCpuLimitRule."""
        rule = MissingCpuLimitRule()
        
        # Should apply to CPU limit columns
        assert rule.applies_to({
            'column_name': 'CPU_lim_m'
        }) is True
        
        # Should trigger WARNING for missing values
        result = rule.evaluate({
            'cell_value': '',
            'column_name': 'CPU_lim_m'
        })
        assert result.rule_type == RuleType.WARNING
        assert 'CPU limit' in result.message
    
    def test_missing_memory_limit_rule(self):
        """Test MissingMemoryLimitRule."""
        rule = MissingMemoryLimitRule()
        
        # Should apply to Memory limit columns
        assert rule.applies_to({
            'column_name': 'Mem_lim_Mi'
        }) is True
        
        # Should trigger WARNING for missing values
        result = rule.evaluate({
            'cell_value': '',
            'column_name': 'Mem_lim_Mi'
        })
        assert result.rule_type == RuleType.WARNING
        assert 'Memory limit' in result.message
    
    def test_image_pull_policy_always_rule(self):
        """Test ImagePullPolicyAlwaysRule."""
        rule = ImagePullPolicyAlwaysRule()
        
        # Should apply to ImagePullPolicy columns
        assert rule.applies_to({
            'column_name': 'Image_Pull_Policy'
        }) is True
        
        # Should trigger WARNING for 'Always' value
        result = rule.evaluate({
            'cell_value': 'Always',
            'column_name': 'Image_Pull_Policy'
        })
        assert result.rule_type == RuleType.WARNING
        assert 'ImagePullPolicy set to Always' in result.message
        
        # Should not trigger for other values
        result = rule.evaluate({
            'cell_value': 'IfNotPresent',
            'column_name': 'Image_Pull_Policy'
        })
        assert result.rule_type == RuleType.NONE
    
    def test_missing_readiness_probe_rule(self):
        """Test MissingReadinessProbeRule."""
        rule = MissingReadinessProbeRule()
        
        # Should apply to ReadinessProbe columns
        assert rule.applies_to({
            'column_name': 'Readiness_Probe'
        }) is True
        
        # Should trigger ERROR for missing values
        missing_values = ['', '-', 'N/A', 'None', 'No', 'False', 'Missing']
        for value in missing_values:
            result = rule.evaluate({
                'cell_value': value,
                'column_name': 'Readiness_Probe'
            })
            assert result.rule_type == RuleType.ERROR
            assert 'ReadinessProbe missing' in result.message
        
        # Should not trigger for valid values
        result = rule.evaluate({
            'cell_value': 'Yes',
            'column_name': 'Readiness_Probe'
        })
        assert result.rule_type == RuleType.NONE


class TestRuleResult:
    """Test RuleResult functionality."""
    
    def test_rule_result_css_class(self):
        """Test CSS class mapping."""
        error_result = RuleResult(RuleType.ERROR)
        assert error_result.css_class == 'error-cell'
        
        warning_result = RuleResult(RuleType.WARNING)
        assert warning_result.css_class == 'warning-cell'
        
        info_result = RuleResult(RuleType.INFO)
        assert info_result.css_class == ''
        
        none_result = RuleResult(RuleType.NONE)
        assert none_result.css_class == ''
    
    def test_rule_result_boolean_evaluation(self):
        """Test boolean evaluation of rule results."""
        assert bool(RuleResult(RuleType.ERROR)) is True
        assert bool(RuleResult(RuleType.WARNING)) is True
        assert bool(RuleResult(RuleType.INFO)) is True
        assert bool(RuleResult(RuleType.NONE)) is False


class TestRulesEngineIntegration:
    """Integration tests for the complete rules engine."""
    
    def test_complete_workflow(self):
        """Test complete workflow from registration to evaluation."""
        # Setup
        registry = RuleRegistry()
        register_official_rules(registry)
        engine = RulesEngine(registry)
        
        # Test scenario 1: Missing CPU request (ERROR)
        context = {
            'cell_value': '',
            'column_name': 'CPU_req_m',
            'row_data': {
                'Kind': 'Deployment',
                'Namespace': 'default',
                'Name': 'test-app'
            },
            'report_type': 'capacity'
        }
        
        result = engine.evaluate_cell(context)
        assert result.rule_type == RuleType.ERROR
        assert result.css_class == 'error-cell'
        assert result.matched_rule == 'missing_cpu_request'
        
        # Test scenario 2: ImagePullPolicy Always (WARNING)
        context = {
            'cell_value': 'Always',
            'column_name': 'Image_Pull_Policy',
            'row_data': {
                'Container': 'web-server'
            },
            'report_type': 'containers'
        }
        
        result = engine.evaluate_cell(context)
        assert result.rule_type == RuleType.WARNING
        assert result.css_class == 'warning-cell'
        assert result.matched_rule == 'image_pull_policy_always'
        
        # Test scenario 3: Valid value (NONE)
        context = {
            'cell_value': '500m',
            'column_name': 'CPU_req_m',
            'row_data': {},
            'report_type': 'capacity'
        }
        
        result = engine.evaluate_cell(context)
        assert result.rule_type == RuleType.NONE
        assert result.css_class == ''
        assert not result
    
    def test_caching_functionality(self):
        """Test that caching works correctly."""
        registry = RuleRegistry()
        register_official_rules(registry)
        engine = RulesEngine(registry)
        
        context = {
            'cell_value': '',
            'column_name': 'CPU_req_m',
            'row_data': {},
            'report_type': 'capacity'
        }
        
        # First evaluation
        result1 = engine.evaluate_cell(context)
        
        # Second evaluation should use cache
        result2 = engine.evaluate_cell(context)
        
        assert result1.rule_type == result2.rule_type
        assert result1.message == result2.message
        assert result1.matched_rule == result2.matched_rule
        
        # Clear cache and test again
        engine.clear_cache()
        result3 = engine.evaluate_cell(context)
        
        assert result3.rule_type == result1.rule_type
