# Sketch - A Python-based interactive drawing program
# Copyright (C) 1997, 1998, 1999, 2000 by Bernhard Herzog
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


#
#	This module defines some functions that set/read/save/load... the
#	settings in config.py
#

import sys, os
import config
from warn import warn_tb, USER
from Sketch import PointType
from Sketch.Lib import util

#
#	Directories..
#

def init_directories(base_dir):
    config.sketch_dir = base_dir
    dirs = ('pixmap_dir', 'fontmetric_dir', 'resource_dir', 'std_res_dir',
	    'plugin_dir')
    join = os.path.join
    for dir in dirs:
        setattr(config, dir, join(base_dir, getattr(config, dir)))
    config.font_path.append(config.fontmetric_dir)
    envfp = os.getenv('SKETCH_FONTPATH')
    if envfp:
        # file names are unicode in the model; environment bytes are
        # utf-8 on the assumed systems (devdocs/string-handling.md)
        config.font_path.extend(util.as_display_name(envfp).split(':'))
    check_path(config.font_path)

    config.plugin_path.append(config.plugin_dir)
    check_path(config.plugin_path)

    config.user_home_dir = util.gethome()
    config.user_config_dir = os.path.join(config.user_home_dir,
					  config.user_config_dir)

def check_path(path):
    # remove all non-directory or non existing entries from path
    path[:] = filter(os.path.isdir, path)

#
#	User Config Settings
#

class _LoadedPreferences(object):
    # Plain attribute bag used only while the preferences file is
    # executed (load_user_preferences).  The file's raw values are
    # collected here, away from the live preferences object, so that
    # nothing compares or publishes them before they are normalized
    # (python2 reads the plain utf-8 string literals of the file as
    # byte strings; the preferences object must only ever see unicode,
    # K2 in devdocs/string-handling.md).
    pass


def _warn_undecodable(key, value):
    sys.stderr.write('Sketch: preferences file: ignoring the value of '
                     '%s, it is not valid utf-8: %r\n' % (key, value))


INVALID = object()  # marker for values that must be dropped


def _decode_item(key, value):
    # Convert one value read from the preferences file to its runtime
    # representation.  This is the only place where the py2
    # str/unicode distinction for preference values is handled: byte
    # strings are decoded strictly as utf-8.  A value that is not
    # valid utf-8 cannot be interpreted; it is dropped with a warning
    # on the console -- except that undecodable entries of lists (e.g.
    # the mru_files list) are skipped individually and image_dir is
    # reset to the current directory.
    if isinstance(value, str):
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            _warn_undecodable(key, value)
            if key == 'image_dir':
                return os.getcwdu()
            return INVALID
    if isinstance(value, list):
        result = []
        for item in value:
            item = _decode_item(key, item)
            if item is not INVALID:
                result.append(item)
        return result
    if isinstance(value, tuple):
        items = []
        for item in value:
            item = _decode_item(key, item)
            if item is INVALID:
                return INVALID
            items.append(item)
        return tuple(items)
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            k = _decode_item(key, k)
            v = _decode_item(key, v)
            if k is not INVALID and v is not INVALID:
                result[k] = v
        return result
    return value


def _mru_list(files):
    # The MRU list always has exactly four slots: the LoadMRU0..3
    # commands in mainwindow.py access mru_files[0..3] unconditionally
    # (name_cb and LoadFromFile), so a shorter list (e.g. from a
    # hand-edited preferences file) would crash them with IndexError.
    files = list(files)[:4]
    while len(files) < 4:
        files.append('')
    return files


def _assign_preferences(values):
    # Assign the normalized values to the live preferences object.  All
    # strings are unicode now, so the __setattr__ comparisons against
    # the (ascii-only) defaults cannot mix bytes and unicode.
    preferences = config.preferences
    for key, value in values.items():
        value = _decode_item(key, value)
        if value is INVALID:
            continue
        if key == 'mru_files' and isinstance(value, list):
            value = _mru_list(value)
        setattr(preferences, key, value)


def load_user_preferences():
    # Load the user specific configuration.
    if os.path.isdir(config.user_config_dir):
        sys.path.insert(0, config.user_config_dir)

    filename = os.path.join(config.user_config_dir, config.user_settings_file)
    if os.path.isfile(filename):
        # Execute the file into an intermediate object and convert the
        # values before they reach the live preferences object (see
        # _LoadedPreferences).  The str/unicode conversion happens
        # right at the input boundary; under python3 all strings are
        # unicode and it disappears.
        loaded = _LoadedPreferences()
        try:
            execfile(filename, {'preferences': loaded})
        except:
            warn_tb(USER, "Cannot read the preferences file")
        else:
            _assign_preferences(loaded.__dict__)
    try:
        import userhooks
    except ImportError:
        tb = sys.exc_info()[2]
        try:
            if tb.tb_next is not None:
                # The ImportError exception was raised from inside the
                # userhooks module.
                warn_tb(USER, "Cannot import the userhooks file")
            else:
                # There's no userhooks module.
                pass
        finally:
            del tb
    except:
        warn_tb(USER, "Cannot import the userhooks file")


def _string_repr(s):
    # Serialize one string as a plain '...' literal with the characters
    # written directly: the preferences file is utf-8 (declared by the
    # coding cookie written by save_user_preferences) and it uses the
    # same plain-literal syntax under python2 and python3, where no
    # conversion is needed at all.  Only the backslash, the single
    # quote and C0 control characters are escaped; non-ascii characters
    # are never escaped (no u'...' prefix, no \x byte escapes).
    result = []
    for char in s:
        if char in ('\\', "'"):
            result.append('\\' + char)
        elif char == '\n':
            result.append('\\n')
        elif char == '\r':
            result.append('\\r')
        elif char == '\t':
            result.append('\\t')
        elif ord(char) < 0x20:
            result.append('\\x%02x' % ord(char))
        else:
            result.append(char)
    return "'%s'" % ''.join(result)


def save_repr(obj):
    # Serialize a preferences value.  Strings are written as plain
    # utf-8 literals (_string_repr); byte-string stragglers (e.g.
    # ascii-only values returned by stock _tkinter) are decoded first,
    # so the file contains only plain string literals.  Containers are
    # converted recursively.  (.sk documents keep using util.skrepr
    # with its \x-escaped byte reprs for master compatibility; the
    # preferences file is read and written only here, so it can use
    # the plain utf-8 format.)
    if type(obj) == PointType:
        return 'Point(%g, %g)' % tuple(obj)
    if isinstance(obj, str):
        obj = util.as_display_name(obj)
    if isinstance(obj, unicode):
        return _string_repr(obj)
    if isinstance(obj, list):
        return '[%s]' % ', '.join([save_repr(item) for item in obj])
    if isinstance(obj, tuple):
        if len(obj) == 1:
            return '(%s,)' % save_repr(obj[0])
        return '(%s)' % ', '.join([save_repr(item) for item in obj])
    if isinstance(obj, dict):
        return '{%s}' % ', '.join(
            ['%s: %s' % (save_repr(key), save_repr(value))
             for key, value in obj.items()])
    return repr(obj)


def save_user_preferences():

    preferences = config.preferences
    if len(preferences.__dict__) == 0:
        return

    filename = os.path.join(config.user_config_dir, config.user_settings_file)
    try:
        util.create_directory(config.user_config_dir)
        file = open(filename, 'wb')
    except (IOError, os.error) as value:
        sys.stderr.write('cannot write preferences into %s: %s\n'
                         % (util.as_display_name(filename), value[1]))
        return

    # The file is utf-8: the header declares it (see _string_repr) and
    # the text is encoded explicitly before it is written.
    lines = ['#### -*- coding: utf-8 -*-\n'
             '# This file was automatically created by Sketch.\n\n']

    defaults = config.ProgramDefaults.__dict__
    items = preferences.__dict__.items()
    items.sort()
    for key, value in items:
        if key in defaults and defaults[key] == value:
            continue
        lines.append('preferences.%s = %s\n' % (key, save_repr(value)))
    try:
        file.write(''.join(lines).encode('utf-8'))
        file.close()
    except (IOError, os.error) as value:
        sys.stderr.write('cannot write preferences into %s: %s\n'
                         % (util.as_display_name(filename), value[1]))

def add_program_default(key, value):
    setattr(config.ProgramDefaults, key, value)

def get_preference(key, default):
    if hasattr(config.preferences, key):
        return getattr(config.preferences, key)
    return default

def add_mru_file(filename):
    if not filename:
        return
    mru_list = config.preferences.mru_files
    if filename in mru_list:
        mru_list.remove(filename)
    mru_list.insert(0, filename)
    config.preferences.mru_files = _mru_list(mru_list)

def remove_mru_file(filename):
    if not filename:
        return
    mru_list = config.preferences.mru_files
    if filename in mru_list:
        mru_list.remove(filename)
        config.preferences.mru_files = _mru_list(mru_list)




#
#	Add options to the Tk Option database
#

def add_options(root):
    root.option_readfile(os.path.join(config.std_res_dir, config.tk_defaults),
			 'startupFile')
