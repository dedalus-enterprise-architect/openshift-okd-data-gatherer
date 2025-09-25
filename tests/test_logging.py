from data_gatherer.util import logging as log
import sys
from io import StringIO


def test_logging_level_filtering():
    # Capture stderr
    old_stderr = sys.stderr
    captured_output = StringIO()
    sys.stderr = captured_output
    
    try:
        # Configure to INFO level
        log.configure_logging('INFO', 'json')
        
        # DEBUG should be filtered out
        log.debug('debug message')
        assert captured_output.getvalue() == ''
        
        # INFO should pass through
        log.info('info message')
        assert 'info message' in captured_output.getvalue()
        
        # Reset
        captured_output.truncate(0)
        captured_output.seek(0)
        
        # Configure to DEBUG level
        log.configure_logging('DEBUG', 'json')
        
        # Now DEBUG should pass through
        log.debug('debug message')
        assert 'debug message' in captured_output.getvalue()
        
    finally:
        sys.stderr = old_stderr


def test_logging_format_text():
    old_stderr = sys.stderr
    captured_output = StringIO()
    sys.stderr = captured_output
    
    try:
        log.configure_logging('INFO', 'text')
        log.info('test message', key='value')
        output = captured_output.getvalue()
        
        # Should be text format, not JSON
        assert '[INFO]' in output
        assert 'test message' in output
        assert 'key=value' in output
        assert not output.startswith('{')  # Not JSON
        
    finally:
        sys.stderr = old_stderr


def test_logging_format_json():
    old_stderr = sys.stderr
    captured_output = StringIO()
    sys.stderr = captured_output
    
    try:
        log.configure_logging('INFO', 'json')
        log.info('test message', key='value')
        output = captured_output.getvalue().strip()
        
        # Should be JSON format
        assert output.startswith('{')
        assert '"level": "INFO"' in output
        assert '"msg": "test message"' in output
        assert '"key": "value"' in output
        
    finally:
        sys.stderr = old_stderr
