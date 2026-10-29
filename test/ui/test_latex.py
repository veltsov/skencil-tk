# -*- coding: utf-8 -*-
# Layer 3: LaTeX plugin recompilation with non-ASCII text.  Runs the
# full application under Xvfb and triggers LtxObj.recompute with a
# unicode text parameter, exercising utf-8 through the external
# toolchain (pdflatex/latex + pstoedit + gs) and the save path.
# Skipped when the external tools are not installed.


import os
import re

from distutils.spawn import find_executable

import pytest

import testsupport

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')

# '\sf Текст проверка' with a preamble declaring the font encoding, in
# the plugin's \preamble<char>...<char> syntax.  When pscyr (as in the
# rustext.sk fixture) is available it is used -- otherwise the T2A
# fonts fall back to Type 3 bitmaps, which pstoedit cannot interpret
# (empty render); with cm-super installed the plain T2A variant works.
def _kpsewhich(filename):
    try:
        from subprocess import Popen, PIPE
        po = Popen(['kpsewhich', filename], stdout=PIPE, stderr=PIPE)
        return bool(po.communicate()[0].strip())
    except OSError:
        return False

if _kpsewhich('pscyr.sty'):
    LTX_TEXT = ('\\preamble|\\usepackage{pscyr}\\usepackage[T2A]{fontenc}|\n'
                '\\sf \u0422\u0435\u043a\u0441\u0442 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430')
else:
    LTX_TEXT = ('\\preamble|\\usepackage[T2A]{fontenc}|\n'
                '\\sf \u0422\u0435\u043a\u0441\u0442 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430')


def latex_available():
    for tool in (os.environ.get('GS') or 'gs',
                 'pstoedit', 'pdflatex', 'latex', 'dvips'):
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
           'SKENCIL_LTX_TEXT': LTX_TEXT,
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
    leaked = re.search(rb"(?<![A-Za-z_])u['\"]", data)
    assert leaked is None, \
        'unicode string leaked into %s: %r...' \
        % (out, data[leaked.start():][:40])
    # the unicode parameter must be saved in master's utf-8 \x-escape form
    expected = repr(LTX_TEXT.encode('utf-8'))[1:-1].encode('ascii')
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
        # the plugin parameter text is K2: unicode in the model after
        # the reader boundary decode (devdocs/string-handling.md)
        assert texts == [LTX_TEXT], repr(texts)
        assert isinstance(texts[0], str), repr(texts)
        for obj in testsupport.iter_objects(doc2):
            if obj.__class__.__name__ == 'LtxObj':
                assert len(obj.objects) > 0, 'recompiled object is empty'
                break
    else:
        assert 'LTXGROUP:empty' in stdout, stdout
        print('NOTE: pstoedit produced no objects (pstoedit 3.78 Sketch '
              'driver regression); the utf-8 path through pdflatex/'
              'pstoedit was still exercised and the parameter was saved')
