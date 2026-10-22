# Layer 3: LaTeX plugin recompilation with non-ASCII text.  Runs the
# full application under Xvfb and triggers LtxObj.recompute with a
# unicode text parameter, exercising utf-8 through the external
# toolchain (pdflatex/latex + pstoedit + gs) and the save path.
# Skipped when the external tools are not installed.

from __future__ import print_function

import os
import re

from distutils.spawn import find_executable

import pytest

import testsupport

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')

# like the fixture: preamble declaring the T2A cyrillic font encoding,
# followed by the non-ASCII text ('\preamble<char>...<char>' syntax of
# the plugin); '\sf Текст проверка'
LTX_TEXT = (u'\\preamble|\\usepackage[T2A]{fontenc}|\n'
            u'\\sf \u0422\u0435\u043a\u0441\u0442 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430')


def latex_available():
    for tool in ('gs', 'pstoedit', 'pdflatex', 'latex', 'dvips'):
        if find_executable(tool) is None:
            return False
    return True

pytestmark = pytest.mark.skipif(
    not latex_available(),
    reason='LaTeX toolchain (latex/pdflatex, pstoedit, gs) not installed')


def test_latex_recompile_unicode():
    out = testsupport.output_path('sk', 'rustext_latex.sk')
    script = os.path.join(SCRIPTS, 'latex_recompile.py')
    env = {'SKENCIL_TEST_HEADLESS': '1',
           'SKENCIL_LTX_TEXT': LTX_TEXT.encode('utf-8'),
           'SKENCIL_LTX_OUT': out}
    rc, app_out, app_err = testsupport.run_app(
        [testsupport.data_path('rustext.sk')],
        script=script, script_env=env, timeout=240)
    stdout = app_out.decode('utf-8', 'replace')
    stderr = app_err.decode('utf-8', 'replace')
    assert rc == 0, ('application exited with %d\nstdout:\n%s\nstderr:\n%s'
                     % (rc, stdout, stderr))
    assert 'LTXGROUP:error' not in stdout, \
        'recompute raised an exception\nstdout:\n%s' % stdout

    assert os.path.exists(out), 'document was not saved'
    with open(out, 'rb') as f:
        data = f.read()
    leaked = re.search(r"(?<![A-Za-z_])u['\"]", data)
    assert leaked is None, \
        'unicode string leaked into %s: %r...' \
        % (out, data[leaked.start():][:40])
    # the unicode parameter must be saved in master's utf-8 \x-escape form
    expected = repr(LTX_TEXT.encode('utf-8'))[1:-1]
    assert expected in data, 'utf-8 text not saved in \\x-escaped form'

    # rendering: pstoedit 3.78's Sketch driver is broken (returns an
    # empty document for any input, even trivial PostScript); an empty
    # plugin compound is then deliberately not loaded again
    # (Sketch/Base/load.py check_object ignores empty plugins), so the
    # text round trip can only be asserted with a working driver
    if 'LTXGROUP:ok' in stdout:
        doc2 = testsupport.load_document(out)
        texts = [obj.Text() for obj in testsupport.iter_objects(doc2)
                 if obj.__class__.__name__ == 'LtxObj']
        assert texts == [LTX_TEXT.encode('utf-8')], repr(texts)
        for obj in testsupport.iter_objects(doc2):
            if obj.__class__.__name__ == 'LtxObj':
                assert len(obj.objects) > 0, 'recompiled object is empty'
                break
    else:
        assert 'LTXGROUP:empty' in stdout, stdout
        print('NOTE: pstoedit produced no objects (pstoedit 3.78 Sketch '
              'driver regression); the utf-8 path through pdflatex/'
              'pstoedit was still exercised and the parameter was saved')
