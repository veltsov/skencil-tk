# -*- coding: utf-8 -*-

# Routines for UI fonts & colors management

# Copyright (c) 2010 by Igor E.Novikov
#
#This library is free software; you can redistribute it and/or
#modify it under the terms of the GNU Library General Public
#License as published by the Free Software Foundation; either
#version 2 of the License, or (at your option) any later version.
#
#This library is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#Library General Public License for more details.
#
#You should have received a copy of the GNU Library General Public
#License along with this library; if not, write to the Free Software
#Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# Remove gtk stuff.

import os, string, copy, sys
from tempfile import NamedTemporaryFile


##################################################
# Font routines
##################################################

def set_ui_font(widget, font_name):
    """
    Applies font to tk defaults.
    """
    if font_name is not None:
        widget.tk.call('option', 'add', '*font', font_name)


##################################################
# Colors routines
##################################################

BUILTIN_SCHEME = 'Built-in'

def tkcolor_to_rgb(tkcolor):
    """
    Converts tk color string as tuple of integer values.
    For example: #ff00ff => (255,0,255)
    """
    return (int(tkcolor[1:3], 0x10), int(tkcolor[3:5], 0x10), int(tkcolor[5:], 0x10))

def saturated_color(color):
    """
    Returns saturated color value. 
    """
    r, g, b = tkcolor_to_rgb(color)
    delta = 255 - max(r, g, b)
    return '#%02X%02X%02X' % (r + delta, g + delta, b + delta)
                
def middle_color(dark, light, factor=0.5):
    """
    Calcs middle color value.
    
    dark, light - tk color strings
    factor - resulted color shift 
    """
    dark = tkcolor_to_rgb(dark)
    light = tkcolor_to_rgb(light)
    r = dark[0] + (light[0] - dark[0]) * factor
    g = dark[1] + (light[1] - dark[1]) * factor
    b = dark[2] + (light[2] - dark[2]) * factor
    return '#%02X%02X%02X' % (r, g, b)

def lighter_color(color, factor):
    """
    Calcs lighted color value according factor.
    
    color - tk color strings
    factor - resulted color shift   
    """
    return middle_color(color, saturated_color(color), factor)

class ColorScheme:
    """
    The class represents UI color scheme.
    Colors can be imported from system (SYSTEM_SCHEME)
    or built-in values (BUILTIN_SCHEME).
    """
    
    bg = '#d4d0c8'
    fg = '#000000'
    highlightbackground = '#f3f2ef'
    highlightcolor = '#b0ada5'
    disabledforeground = '#b0ada6'
    selectbackground = '#002468'
    selectforeground = '#ffffff'
    
    menubackground = '#dedad2'
    menuforeground = '#000000'
    menuselectbackground = '#002468'
    menuselectforeground = '#ffffff'
    menudisabledforeground = '#b0ada6'
    menubordercolor = '#7e7b77'
    
    editfieldbackground = '#ffffff'
    editfieldforeground = '#000000'
    treelinescolor = '#000000'

    radiobuttonselectcolor = '#ffffff'
    
    d3_light = '#ffffff'
    d3_dark = '#b0ada6'
    
    light_border = '#b0ada6'
    normal_border = '#b0ada6'
    dark_border = '#b0ada6'
    
    evencolor = '#f0f0f0'
    
    name = BUILTIN_SCHEME
    
def set_ui_colors(widget, color_scheme):
    """
    Applies ColorScheme object values to tk defaults.
    """
    if color_scheme is None:
        color_scheme = ColorScheme()
    
    widget.tk.call('tk_setPalette', color_scheme.bg)
                
    widget.tk.call('option', 'add', '*background', color_scheme.bg, 'interactive')
    widget.tk.call('option', 'add', '*foreground', color_scheme.fg, 'interactive')
    widget.tk.call('option', 'add', '*selectForeground', color_scheme.selectforeground, 'interactive')
    widget.tk.call('option', 'add', '*selectBackground', color_scheme.selectbackground, 'interactive')
    widget.tk.call('option', 'add', '*highlightBackground', color_scheme.highlightbackground, 'interactive')
    widget.tk.call('option', 'add', '*highlightColor', color_scheme.highlightcolor, 'interactive')
    widget.tk.call('option', 'add', '*activeBackground', color_scheme.bg, 'interactive')
    widget.tk.call('option', 'add', '*activeForeground', color_scheme.fg, 'interactive')
    widget.tk.call('option', 'add', '*Menu.activeBackground', color_scheme.selectbackground, 'interactive')
    widget.tk.call('option', 'add', '*Menu.activeForeground', color_scheme.selectforeground, 'interactive')
    
    widget.tk.call('option', 'add', '*Listbox.background', color_scheme.editfieldbackground, 'interactive')
    widget.tk.call('option', 'add', '*Listbox.foreground', color_scheme.editfieldforeground, 'interactive')
    widget.tk.call('option', 'add', '*Entry.background', color_scheme.editfieldbackground, 'interactive')
    widget.tk.call('option', 'add', '*Entry.foreground', color_scheme.editfieldforeground, 'interactive')
  
    widget.tk.call('option', 'add', '*tooltips*background', '#F6F6B9', 'interactive')  
    widget.tk.call('option', 'add', '*tooltips.background', '#C2C24E', 'interactive')
    
    widget.tk.call('option', 'add', '*Menu.background', color_scheme.menubackground, 'interactive')
    widget.tk.call('option', 'add', '*Menu*background', color_scheme.menubackground, 'interactive')
    widget.tk.call('option', 'add', '*Menu.highlightColor', color_scheme.menubordercolor, 'interactive')

    widget.tk.call('option', 'add', '*Radiobutton.selectColor', color_scheme.radiobuttonselectcolor, 'interactive')
    
    widget.tk.call('option', 'add', '*canvas_frame.highlightColor', color_scheme.normal_border, 'interactive')
    widget.tk.call('option', 'add', '*canvas_frame.highlightBackground', color_scheme.normal_border, 'interactive')
     
    widget.tk.call('option', 'add', '*Darkline.background', color_scheme.d3_dark, 'interactive')
    widget.tk.call('option', 'add', '*Lightline.background', color_scheme.d3_light, 'interactive')
