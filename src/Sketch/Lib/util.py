# Sketch - A Python-based interactive drawing program
# Copyright (C) 1997, 1998, 1999, 2002, 2003 by Bernhard Herzog
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307	USA

#
#	Some useful functions used in various places...
#


import os, re, stat
import subprocess

def popen_write(cmd):
    """Run CMD through the shell and return a file object connected to
    its standard input. Replacement for os.popen(cmd, 'w')."""
    if isinstance(cmd, str):
        # py2's os layer encodes process arguments with the default
        # (ascii) codec; the shell command may contain utf-8 file names
        # (K2/K6, devdocs/string-handling.md)
        cmd = cmd.encode('utf-8')
    return subprocess.Popen(cmd, shell=True,
                            stdin=subprocess.PIPE).stdin

def popen_read(cmd):
    """Run CMD through the shell and return a file object connected to
    its standard output. Replacement for os.popen(cmd)."""
    if isinstance(cmd, str):
        cmd = cmd.encode('utf-8')
    return subprocess.Popen(cmd, shell=True,
                            stdout=subprocess.PIPE).stdout

# Return the value of the environment variable S if present, None
# otherwise. In Python 1.5 one might use os.environ.get(S) instead...
def getenv(s):
    if s in os.environ:
        return os.environ[s]
    return None


# Return the ghostscript interpreter command: $GS if set, else plain
# 'gs'.  The GS variable is also honored by pstoedit's ghostscript
# frontend (verified with pstoedit 3.78), so a single setting selects
# the interpreter for the whole toolchain.  This is used e.g. by the
# AppImage, which bundles a self-contained interpreter as `skgs' (not
# `gs', so that the Ubuntu AppArmor profile for the system gs, which
# prevents reading font files from user directories, does not apply).
def ghostscript_command():
    return os.environ.get('GS') or 'gs'


def _gs_command(args):
    # the full command line for the given ghostscript arguments
    return [ghostscript_command()] + list(args)


def run_gs(args):
    """Run the ghostscript interpreter with ARGS (a list of command
    line arguments, without the program name; no shell involved, so
    arguments with spaces need no quoting) and wait for it.  Return
    the exit status."""
    return subprocess.call(_gs_command(args))


def run_gs_pipe(args):
    """Run the ghostscript interpreter with ARGS and return a file
    object connected to its standard input, for piping PostScript into
    it (like popen_write, but without a shell)."""
    return subprocess.Popen(_gs_command(args),
                            stdin=subprocess.PIPE).stdin


def run_gs_output(args):
    """Run the ghostscript interpreter with ARGS and return a tuple
    (exit status, combined standard output and error as unicode)."""
    po = subprocess.Popen(_gs_command(args), stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = po.communicate()
    # the output ends up in warning messages (str); undecodable bytes
    # are replaced
    return po.returncode, (out + err).decode('utf-8', 'replace')


# Return the pwd entry for the current user in the format of
# pwd.getpwuid.
def get_pwd():
    import pwd
    user = getenv("USER") or getenv("LOGNAME")
    if not user:
        return pwd.getpwuid(os.getuid())
    else:
        return pwd.getpwnam(user)

# Return the user's home directory. If it can't be determined from the
# environment or from the password database, return the current
# directory.
def gethome():
    try:
        home = getenv("HOME")
        if not home:
            home = get_pwd()[5]
        # file names are unicode in the model; the filesystem
        # representation is assumed to be utf-8 (see
        # devdocs/string-handling.md)
        return as_unicode(home)
    except (KeyError, ImportError):
        return os.curdir

# Return the real user name (the gecos field of passwd)
def get_real_username():
    try:
        return get_pwd()[4]
    except:
        return None

# Return the hostname
def gethostname():
    name = getenv('HOSTNAME')
    if not name:
        try:
            import socket
            name = socket.gethostname()
        except:
            pass
    return name


# sh_quote taken almost verbatim from the python standard library with
# the only difference that it doesn't prepend a space
def sh_quote(x):
    """Return a unix shell quoted version of the string x.

    The result is of a form that can be inserted into an argument to
    os.system so that it looks like a single word to the shell.
    """
    # Two strategies: enclose in single quotes if it contains none;
    # otherwise, enclose in double quotes and prefix quotable characters
    # with backslash.
    if '\'' not in x:
        return '\'' + x + '\''
    s = '"'
    for c in x:
        if c in '\\$"`':
            s = s + '\\'
        s = s + c
    s = s + '"'
    return s


#
#	Filename manipulation
#

# return the longest common prefix of path1 and path2 that is a
# directory.
def commonbasedir(path1, path2):
    if path1[-1] != os.sep:
        path1 = path1 + os.sep
    return os.path.split(os.path.commonprefix([path1, path2]))[0]



# return the absolute path PATH2 as a path relative to the directory
# PATH1. PATH1 must be an absoulte filename. If commonbasedir(PATH1,
# PATH2) is '/', return PATH2. Doesn't take symbolic links into
# account...
def relpath(path1, path2):
    if not os.path.isabs(path2):
        return path2
    basedir = commonbasedir(path1, path2)
    if basedir == os.sep:
        return path2
    path2 = path2[len(basedir) + 1 : ]
    curbase = path1
    while curbase != basedir:
        curbase = os.path.split(curbase)[0]
        path2 = os.pardir + os.sep + path2
    return path2


# find a file FILE in one of the directories listed in PATHS. If a file
# is found, return its full name, None otherwise.
def find_in_path(paths, file):
    for path in paths:
        fullname = os.path.join(path, file)
        if os.path.isfile(fullname):
            return fullname

# find one of the files listed in FILES in one of the directories in
# PATHS. Return the name of the first one found, None if no file is
# found.
def find_files_in_path(paths, files):
    for path in paths:
        for file in files:
            fullname = os.path.join(path, file)
            if os.path.isfile(fullname):
                return fullname


# Create the directory dir and its parent dirs when necessary
def create_directory(dir):
    if os.path.isdir(dir):
        return

    parent, base = os.path.split(dir)
    create_directory(parent)
    os.mkdir(dir, 0o777)

# Make a backup of FILENAME if it exists by renaming it to its
# backupname (a ~ appended)

class BackupError(Exception):
    def __init__(self, errno, strerror, filename = ''):
        self.errno = errno
        self.strerror = strerror
        self.filename = filename


def make_backup(filename):
    if os.path.isfile(filename):
        backupname = filename + '~'
        try:
            os.rename(filename, backupname)
        except os.error as value:
            raise BackupError(value[0], value[1], backupname)

#
#
#

# Return the current local date and time as a string. The optional
# parameter format is used as the format parameter of time.strftime and
# defaults to '%c'.
# Currently this is used for the CreationTime comment in a PostScript
# file.
def current_date(format = '%c'):
    import time
    return time.strftime(format, time.localtime(time.time()))


#
#
#

#An empty class...
class Empty:
    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)

#
#	List Manipulation
#

def flatten(lst):
    result = []
    for item in lst:
        if isinstance(item, list):
            result = result + flatten(item)
        else:
            result.append(item)
    return result


#
#       String Manipulation
#

rx_format = re.compile(r'%\((?P<item>[a-zA-Z_0-9]+)\)'
                       r'\[(?P<converter>[a-zA-Z_]+)\]')

def as_unicode(s):
    # Byte strings at runtime are utf-8 encoded (see
    # devdocs/unicode-runtime-audit.md).  Convert them for safe mixing
    # with the gettext templates; other types pass through unchanged.
    # python3: only bytes need conversion.
    if isinstance(s, bytes):
        return s.decode('utf-8')
    return s

def decode_sk_string(s):
    # Reader-boundary conversion for the .sk format.  User-provided
    # strings (layer/guide/grid names, style names, paper format names)
    # are stored in .sk files as utf-8 encoded byte strings in repr()
    # form (\x escapes, no u prefix) and become unicode in the model
    # right here; the model must never see byte strings for them.
    # Text object contents (txt/pt) and file names (bm/eps) stay byte
    # strings -- their bytes are in the font's encoding resp. the
    # filesystem encoding.  Plugin object parameters are normalized by
    # the plugin objects themselves (they know the kind of their text).
    # See devdocs/string-handling.md.
    # python3: str is already unicode; byte strings (from .sk files,
    # font-encoded text) are utf-8 and are decoded.
    if isinstance(s, bytes):
        return s.decode('utf-8')
    return s

def as_latin1_text(s):
    # Display conversion for font-encoded text bytes (the `text'
    # attribute of SimpleText/PathText: one byte per character in the
    # font's encoding).  These bytes are NOT utf-8; map them 1:1 onto
    # U+0000..U+00FF.  latin-1 decoding never fails, so this cannot
    # raise and cannot split a character.
    if isinstance(s, bytes):
        return s.decode('latin-1')
    return s

def as_display_name(s):
    # Display conversion for file name byte strings (K4).  The
    # filesystem name representation is assumed to be utf-8 (see
    # devdocs/string-handling.md); decode leniently -- undecodable
    # bytes (e.g. from a foreign-encoding command line argument) are
    # replaced instead of raising.
    # python3: os.environ/argv give str already.
    if isinstance(s, bytes):
        return s.decode('utf-8', 'replace')
    return s


def skrepr(s):
    # Serialization form for strings in text files written by Sketch
    # (.sk documents, the preferences file): utf-8 encoded byte strings
    # in repr() form (\x escapes, no u'...' prefix).  Unicode strings
    # (e.g. layer names coming from gettext) must be converted
    # explicitly; otherwise they would be saved as u'...' with \u
    # escapes, which the .sk reader (parse_sk_line2) cannot read and
    # which master never wrote.
    # python3: encode to utf-8 and use the repr of the bytes object
    # with the b-prefix stripped (byte-identical to the python2 form).
    if isinstance(s, str):
        s = s.encode('utf-8')
    r = repr(s)
    if r[0] == 'b':
        r = r[1:]
    return r

def format(template, converters, dict):
    # Normalize everything to unicode: the templates come from the
    # gettext shim (unicode), the values may be byte strings (utf-8)
    # from the document or the file system.  Mixing both in py2's %
    # operator raises UnicodeDecodeError.  The result is always
    # unicode, which the Tk widgets display correctly.
    template = as_unicode(template)
    udict = {}
    for key, value in dict.items():
        udict[key] = as_unicode(value)
    result = []
    pos = 0
    while pos < len(template):
        match = rx_format.search(template, pos)
        if match:
            result.append(template[pos:match.start()] % udict)
            converter = converters[match.group('converter')]
            item = udict[match.group('item')]
            result.append(as_unicode(converter(item)))
            pos = match.end()
        else:
            result.append(template[pos:] % udict)
            pos = len(template)

    return ''.join(result)

# convert a bitmap to a string containing an xbm file. The linedlg uses
# this for instance to convert bitmap objects to Tk bitmap images.
def xbm_string(bitmap):
    width, height = bitmap.GetGeometry()[3:5]
    lines = ['#define sketch_width %d' % width,
             '#define sketch_height %d' % height,
             'static unsigned char sketch_bits[] = {']
    lines = lines + bitmap.GetXbmStrings() + ['}', '']
    return '\n'.join(lines)
