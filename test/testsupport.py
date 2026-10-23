# Shared support for the skencil-tk test suite.
#
# Python 2.7 compatible (must run under the interpreter that runs the
# application).  Used by the pytest suites, test/record.py, add-fixture
# and run_tests.sh.
#
# Baselines are generated from a fixed revision of the `master` branch
# (see test/baselines/BASELINE-REV and devdocs/testing.md).  Two
# environment variables control the suite:
#
#   SKENCIL_TEST_BUILD   path to a build tree (the directory containing
#                        lib.*-2.7 and scripts-2.7); defaults to
#                        <repo>/build.  Set by run_tests.sh --record to
#                        point at the baseline (master) worktree build.
#   SKENCIL_TEST_RECORD  if set to `1', golden artifacts are (re)written
#                        instead of compared.

from __future__ import print_function

import glob
import os
import shutil
import subprocess
import sys

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TEST_DIR)
DATA_DIR = os.path.join(TEST_DIR, 'data')
BASELINE_DIR = os.path.join(TEST_DIR, 'baselines')
OUTPUT_DIR = os.path.join(TEST_DIR, 'output')
MANIFEST = os.path.join(DATA_DIR, 'fixtures.txt')
BASELINE_REV_FILE = os.path.join(BASELINE_DIR, 'BASELINE-REV')

RECORD = os.environ.get('SKENCIL_TEST_RECORD') == '1'


# ---------------------------------------------------------------- builds

def build_root():
    env = os.environ.get('SKENCIL_TEST_BUILD')
    if env:
        return env
    return os.path.join(REPO_ROOT, 'build')


def build_lib():
    """The lib.*-2.7 directory with the compiled Sketch package."""
    pattern = os.path.join(build_root(), 'lib.*-2.7')
    candidates = sorted(glob.glob(pattern))
    if not candidates:
        raise RuntimeError('no build tree found under %s '
                           '(run `python2 setup.py build` first)'
                           % build_root())
    return candidates[0]


def build_scripts():
    return os.path.join(build_root(), 'scripts-2.7')


_sketch_module = None


def sketch():
    """Import and initialize Sketch (headless, no Tk) and return the
    module.  Safe to call repeatedly."""
    global _sketch_module
    if _sketch_module is None:
        sys.path.insert(0, build_lib())
        import Sketch
        Sketch.init_lib()
        _sketch_module = Sketch
    return _sketch_module


def load_document(path):
    sketch()
    from Sketch.Base import load
    return load.load_drawing(path)


# -------------------------------------------------------------- fixtures

def fixtures():
    with open(MANIFEST) as f:
        return [line.strip() for line in f
                if line.strip() and not line.startswith('#')]


def data_path(name):
    return os.path.join(DATA_DIR, name)


# ---------------------------------------------------------------- output

def output_dir(kind):
    dir = os.path.join(OUTPUT_DIR, kind)
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return dir


def output_path(kind, name):
    return os.path.join(output_dir(kind), name)


def baseline_path(kind, name):
    dir = os.path.join(BASELINE_DIR, kind)
    if not os.path.isdir(dir):
        os.makedirs(dir)
    return os.path.join(dir, name)


# ------------------------------------------------------- external tools

def sk2ps(infile, outfile):
    """Convert a drawing to PostScript with the sk2ps script of the
    build tree under test.  Deterministic header values are forced."""
    script = os.path.join(build_scripts(), 'sk2ps')
    cmd = [sys.executable, script,
           '-t', 'test', '-d', 'Jan  1 00:00:00 2026', '-f', 'test',
           infile, outfile]
    subprocess.check_call(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)


def gs_rasterize(src, png, dpi=100):
    """Rasterize PS/EPS/PDF to PNG with ghostscript, cropped to the
    bounding box for EPS input."""
    cmd = ['gs', '-dSAFER', '-dBATCH', '-dNOPAUSE', '-dQUIET',
           '-sDEVICE=png16m', '-r%d' % dpi,
           '-dEPSCrop', '-sOutputFile=%s' % png, src]
    subprocess.check_call(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)


# ---------------------------------------------------------- comparisons

def normalize_text(text):
    return '\n'.join([line.rstrip() for line in text.splitlines()]) + '\n'


def normalize_sk(text):
    """Normalize the unstable parts of a saved .sk file:
    - the id() of image data objects embedded in bm()/im() directives
      is a memory address and never reproducible;
    - external file references are stored as absolute paths.
    """
    import re
    text = normalize_text(text)
    text = text.replace(DATA_DIR + '/', '<DATA>/')
    text = re.sub(r"\d{12,}", "ID", text)
    return text


def images_differ(path_a, path_b, tol=10, max_frac=0.002):
    """Return (differ, message).  Two images match if they have the same
    size and the fraction of pixels differing by more than `tol' (per
    channel max) is at most `max_frac'."""
    from PIL import Image, ImageChops
    a = Image.open(path_a).convert('RGB')
    b = Image.open(path_b).convert('RGB')
    if a.size != b.size:
        return True, 'size %s != %s' % (a.size, b.size)
    diff = ImageChops.difference(a, b).convert('L')
    hist = diff.histogram()
    changed = sum(hist[tol + 1:])
    frac = changed / float(a.size[0] * a.size[1])
    if frac > max_frac:
        return True, '%.4f of pixels differ (allowed %.4f)' % (frac, max_frac)
    return False, 'ok (%.5f differing)' % frac


def compare_text(kind, name, path, normalize=None):
    """Record or compare a text artifact.  The text is whitespace-
    normalized; `normalize' can be a callable applying additional
    normalization (e.g. normalize_sk for .sk files)."""
    with open(path) as f:
        current = (normalize or normalize_text)(f.read())
    golden = baseline_path(kind, name)
    if RECORD:
        with open(golden, 'w') as f:
            f.write(current)
        return 'recorded %s' % golden
    if not os.path.exists(golden):
        raise AssertionError('no baseline %s; run `test/run_tests.sh '
                             '--record` first' % golden)
    with open(golden) as f:
        expected = normalize_text(f.read())
    assert current == expected, \
        '%s does not match baseline %s' % (path, golden)
    return 'matches %s' % golden


def compare_eps(kind, name, path):
    """Record or compare a PostScript/EPS artifact.  Byte comparison
    first; if the bytes differ (harmless header/number formatting), the
    files are rasterized with ghostscript and compared as images."""
    golden = baseline_path(kind, name + '.eps')
    if RECORD:
        shutil.copyfile(path, golden)
        png = baseline_path(kind, name + '.png')
        gs_rasterize(golden, png)
        return 'recorded %s' % golden
    if not os.path.exists(golden):
        raise AssertionError('no baseline %s; run `test/run_tests.sh '
                             '--record` first' % golden)
    with open(path) as f:
        current = f.read()
    with open(golden) as f:
        expected = f.read()
    if normalize_text(current) == normalize_text(expected):
        return 'matches %s (byte-identical)' % golden
    # fall back to visual comparison
    current_png = output_path(kind, name + '.png')
    gs_rasterize(path, current_png)
    golden_png = baseline_path(kind, name + '.png')
    if not os.path.exists(golden_png):
        raise AssertionError('no baseline %s; run `test/run_tests.sh '
                             '--record` first' % golden_png)
    differ, msg = images_differ(golden_png, current_png)
    assert not differ, '%s differs from baseline %s: %s' % (path, golden, msg)
    return 'matches %s (raster)' % golden


def compare_image(kind, name, path, tol=10, max_frac=0.002):
    """Record or compare a screenshot PNG."""
    golden = baseline_path(kind, name)
    if RECORD:
        shutil.copyfile(path, golden)
        return 'recorded %s' % golden
    if not os.path.exists(golden):
        raise AssertionError('no baseline %s; run `test/run_tests.sh '
                             '--record` first' % golden)
    differ, msg = images_differ(golden, path, tol=tol, max_frac=max_frac)
    assert not differ, '%s differs from baseline %s: %s' % (path, golden, msg)
    return 'matches %s' % golden


# ----------------------------------------------------- document helpers

def iter_objects(container):
    """Yield every object in a document, layer or compound, depth
    first."""
    if hasattr(container, 'objects'):
        children = container.objects
    else:  # a document: iterate its layers
        for layer in container.layers:
            for obj in iter_objects(layer):
                yield obj
        return
    for obj in children:
        yield obj
        if obj.is_Compound:
            for child in iter_objects(obj):
                yield child


def class_name(obj):
    # the Sketch classes are old-style (Python 2) classes, so
    # type(obj).__name__ is just 'instance'; use the real class
    return obj.__class__.__name__


def first_bezier(document):
    """The first real PolyBezier object in the document."""
    for obj in iter_objects(document):
        if class_name(obj) == 'PolyBezier':
            return obj
    return None


def objects_of_class(document, class_):
    return [obj for obj in iter_objects(document)
            if class_name(obj) == class_]


# ----------------------------------------------------------- app runner

def run_app(args, script=None, script_env=None, timeout=120):
    """Run the full application under Xvfb.  `args' are extra command
    line arguments (e.g. a file to open).  Returns (returncode, stdout,
    stderr).  Fails the test if the app times out.  (Python 2 has no
    subprocess timeout support, so poll and kill on deadline.)"""
    import tempfile
    import time

    launcher = os.path.join(build_scripts(), 'skencil')
    cmd = ['xvfb-run', '-a', '-s', '-screen 0 1024x768x24',
           sys.executable, launcher, '--geometry=900x650+0+0']
    if script:
        cmd += ['--run-script', script]
    cmd += list(args)
    env = dict(os.environ)
    if script_env:
        env.update(script_env)
    out_file = tempfile.TemporaryFile()
    err_file = tempfile.TemporaryFile()
    # own process group, so that a timeout kill takes down xvfb-run,
    # Xvfb and skencil together
    proc = subprocess.Popen(cmd, stdout=out_file, stderr=err_file, env=env,
                            preexec_fn=os.setsid)
    deadline = time.time() + timeout
    while proc.poll() is None and time.time() < deadline:
        time.sleep(0.05)
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, 9)
        except OSError:
            proc.kill()
        proc.wait()
        out_file.close()
        err_file.close()
        raise AssertionError('application timed out after %ss: %s'
                             % (timeout, ' '.join(cmd)))
    out_file.seek(0)
    err_file.seek(0)
    out = out_file.read()
    err = err_file.read()
    out_file.close()
    err_file.close()
    return proc.returncode, out, err


def assert_clean_exit(args, script=None, script_env=None, timeout=120):
    """Run the app and assert exit status 0 and no Python traceback on
    stderr."""
    rc, out, err = run_app(args, script=script, script_env=script_env,
                           timeout=timeout)
    text = err.decode('utf-8', 'replace')
    assert rc == 0, 'application exited with %d\nstderr:\n%s' % (rc, text)
    assert 'Traceback' not in text, 'traceback on stderr:\n%s' % text
    return out, err
