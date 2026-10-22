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

def load_user_preferences():
    # Load the user specific configuration.
    if os.path.isdir(config.user_config_dir):
        sys.path.insert(0, config.user_config_dir)

    filename = os.path.join(config.user_config_dir, config.user_settings_file)
    if os.path.isfile(filename):
        try:
            execfile(filename, {'preferences':config.preferences})
        except:
            warn_tb(USER, "Cannot read the preferences file")
        normalize_mru_files()
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


def save_repr(obj):
    # Serialize a preferences value the way master wrote its text
    # files: strings as utf-8 encoded byte-string reprs (\x escapes,
    # no u'...' prefix -- util.skrepr, see devdocs/string-handling.md).
    # Containers (e.g. the mru_files list) are converted recursively,
    # because repr() of the container would otherwise emit u'...'
    # items.
    if type(obj) == PointType:
        return 'Point(%g, %g)' % tuple(obj)
    if isinstance(obj, unicode):
        return util.skrepr(obj)
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


def normalize_mru_files():
    # The preferences file stores file names as utf-8 byte strings
    # (see save_repr); execfile reads them back as bytes, while newly
    # opened files add unicode entries.  Normalize the list to unicode
    # (K2) -- otherwise the mixed kinds crash `filename in mru_list'
    # comparisons with UnicodeDecodeError for non-ascii names.
    mru_list = config.preferences.mru_files
    config.preferences.mru_files = [util.as_display_name(filename)
                                    for filename in mru_list]


def save_user_preferences():

    preferences = config.preferences
    if len(preferences.__dict__) == 0:
        return

    filename = os.path.join(config.user_config_dir, config.user_settings_file)
    try:
        util.create_directory(config.user_config_dir)
        file = open(filename, 'w')
    except (IOError, os.error) as value:
        sys.stderr('cannot write preferences into %s: %s'
        	   % (util.as_display_name(filename), value[1]))
        return

    file.write('#### -*- python -*-\n'
	       '# This file was automatically created by Sketch.\n\n')
            #'\nfrom Sketch.config import preferences, Point\n\n')

    defaults = config.ProgramDefaults.__dict__
    items = preferences.__dict__.items()
    items.sort()
    for key, value in items:
        if key in defaults and defaults[key] == value:
            continue
        file.write('preferences.%s = %s\n' % (key, save_repr(value)))

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
    config.preferences.mru_files = mru_list[:4]

def remove_mru_file(filename):
    if not filename:
        return
    mru_list = config.preferences.mru_files
    if filename in mru_list:
        mru_list.remove(filename)
        if len(mru_list) < 4:
            mru_list = mru_list + ['', '', '', '']
        config.preferences.mru_files = mru_list[:4]




#
#	Add options to the Tk Option database
#

def add_options(root):
    root.option_readfile(os.path.join(config.std_res_dir, config.tk_defaults),
			 'startupFile')
