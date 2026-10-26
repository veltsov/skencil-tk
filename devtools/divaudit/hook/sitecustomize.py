# Warning-collector hook for the integer-division audit.
#
# Imported automatically at interpreter start-up when
# devtools/divaudit/hook is on PYTHONPATH (the
# devtools/divaudit/python2-divaudit wrapper puts it there).  Inert
# unless DIVAUDIT_LOG is set.
#
# python2 -Qwarnall emits a DeprecationWarning ("classic int division"
# / "classic float division") at every `/` site with an integer
# operand, carrying the exact file:line.  This hook records
# (file, line, message) tuples with hit counts into DIVAUDIT_LOG (one
# JSON object per line, appended at process exit) and suppresses the
# console spam; all other warnings pass through to the regular handler
# untouched.
#
# Note: a pytest run with the warnings plugin active replaces
# warnings.showwarning per test (warnings.catch_warnings), which
# bypasses this hook; run the suite with `-p no:warnings' under the
# devtools/divaudit/python2-divaudit wrapper.

import json
import os
import sys

try:
    _log_path = os.environ.get('DIVAUDIT_LOG')
    if _log_path:
        import atexit
        import warnings

        _DIV_MESSAGES = ('classic int division', 'classic float division')
        _records = {}
        _logfile = []
        _orig_showwarning = warnings.showwarning

        def _divaudit_showwarning(message, category, filename, lineno,
                                  file=None, line=None):
            try:
                if (category is DeprecationWarning
                        and str(message) in _DIV_MESSAGES):
                    key = (filename, lineno, str(message))
                    _records[key] = _records.get(key, 0) + 1
                    # append immediately: the app payloads may exit via
                    # os._exit(), which skips atexit handlers
                    if not _logfile:
                        _logfile.append(open(_log_path, 'a'))
                    _logfile[0].write(json.dumps({
                        'file': filename,
                        'line': lineno,
                        'message': str(message),
                        'count': 1}) + '\n')
                    _logfile[0].flush()
                    return
            except Exception:
                pass
            _orig_showwarning(message, category, filename, lineno,
                              file, line)

        warnings.showwarning = _divaudit_showwarning

        def _divaudit_dump():
            try:
                if _logfile:
                    _logfile[0].close()
                if _records:
                    sys.stderr.write(
                        'divaudit: %d distinct division sites, %d hits'
                        ' -> %s\n'
                        % (len(_records), sum(_records.values()),
                           _log_path))
            except Exception:
                pass

        atexit.register(_divaudit_dump)
except Exception:
    pass
