/* Sketch - A Python-based interactive drawing program
 * Copyright (C) 1997, 1998, 2002, 2006 by Bernhard Herzog
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Library General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Library General Public License for more details.
 *
 * You should have received a copy of the GNU Library General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */

/*
 *	A Python Object for fontmetrics.
 *
 * A fontmetrics object contains all the information about a scalable
 * font needed to `typeset' some text. It provides some methods that
 * compute various rectangles for given strings.
 *
 * All dimensions are stored as ints in 1000-pixel metric. That means
 * that the ascender of a 12pt instance of a font is 12 * ascender /
 * 1000.0 points, etc.
 *
 * The metrics are indexed by *glyph id* (see devdocs/glyph-text.md):
 * text objects store arrays of indices into the process-global glyph
 * registry, and the string methods accept buffers of native unsigned
 * ints (as provided by array.array('I')) or a single int.  Glyph ids
 * at or beyond the array size are treated as notdef (zero metrics).
 * The mapping between glyph names/ids and font encodings is done in
 * Python code.
 *
 * Fontmetric objects are immutable.
 *
 */

#include <Python.h>
#include <string.h>
#include <structmember.h>

#include "skpoint.h"

/* the metrics for one character */
struct SKCharMetric_s {
    int width;			/* width */
    int llx, lly, urx, ury;	/* bounding box */
};
typedef struct SKCharMetric_s SKCharMetric;

/* the font metrics */
struct SKFontMetric_s {
    PyObject_HEAD
    int			ascender, descender;	/* global ascender/descender */
    int			llx, lly, urx, ury;	/* font bounding box */
    float		italic_angle;		/* italic angle as in afm
						   file */
    int			n_metrics;		/* size of the gid-indexed
						   array */
    SKCharMetric *	char_metric;		/* indexed by glyph id,
						   zero-filled */
};
typedef struct SKFontMetric_s SKFontMetric;

extern DL_IMPORT(PyTypeObject) SKFontMetricType;
#define SKFontMetric_Check(obj) ((v)->ob_type == &SKFontMetricType)


/*
 * Return a new, empty fontmetric object.
 */
PyObject *
SKFontMetric_New()
{
    SKFontMetric * self;

    self = PyObject_New(SKFontMetric, &SKFontMetricType);
    if (self == NULL)
	return NULL;

    self->n_metrics = 0;
    self->char_metric = NULL;

    return (PyObject*)self;
}

static void
skfm_dealloc(SKFontMetric * self)
{
    if (self->char_metric)
	PyMem_Free(self->char_metric);
    PyObject_Del(self);
}

/*
 * Interpret the argument of the string methods: either an object
 * supporting the read buffer protocol whose contents are native
 * unsigned ints (array.array('I')), or a single int giving one glyph
 * id.  Returns 0 on error.
 */
static int
skfm_get_gids(PyObject * object, unsigned int ** gids, int * length)
{
    const void * buffer;
    Py_ssize_t size;

    if (PyInt_Check(object))
    {
	long gid = PyInt_AS_LONG(object);
	if (gid < 0)
	{
	    PyErr_SetString(PyExc_ValueError,
			    "glyph id must be non-negative");
	    return 0;
	}
	/* static singleton: the one-glyph case is consumed
	 * immediately by the caller */
	static unsigned int single;
	single = (unsigned int)gid;
	*gids = &single;
	*length = 1;
	return 1;
    }

    if (PyObject_AsReadBuffer(object, &buffer, &size) < 0)
	return 0;

    if (size % sizeof(unsigned int))
    {
	PyErr_SetString(PyExc_TypeError,
	       "glyph id sequence must be a buffer of native unsigned ints"
	       " (e.g. array.array('I'))");
	return 0;
    }

    *gids = (unsigned int *)buffer;
    *length = (int)(size / sizeof(unsigned int));
    return 1;
}


/*
 * The metric of a gid, or NULL if the gid is beyond the array (treat
 * as notdef).
 */
static SKCharMetric *
skfm_metric_of(SKFontMetric * self, unsigned int gid)
{
    if ((int)gid >= self->n_metrics)
	return NULL;
    return self->char_metric + gid;
}

/*
 *	fm.string_bbox(GIDS)
 *
 * Return the bounding box of the glyphs GIDS as a tuple
 * (llx, lly, urx, ury) in 1000-pixel metric. The first glyph is
 * positioned at (0, 0).
 */
static PyObject *
skfm_string_bbox(SKFontMetric * self, PyObject * args)
{
    PyObject * object;
    unsigned int * gids;
    int length, i;
    int	llx = 0, lly = 0, urx = 0, ury = 0;
    int pos = 0;
    SKCharMetric zero_metric = {0, 0, 0, 0, 0};
    SKCharMetric * metric;

    if (!PyArg_ParseTuple(args, "O", &object))
	return NULL;
    if (!skfm_get_gids(object, &gids, &length))
	return NULL;

    for (i = 0; i < length; i++)
    {
	metric = skfm_metric_of(self, gids[i]);
	if (!metric)
	    metric = &zero_metric;
	if (pos + metric->llx < llx)
	    llx = pos + metric->llx;
	if (pos + metric->urx > urx)
	    urx = pos + metric->urx;
	if (metric->lly < lly)
	    lly = metric->lly;
	if (metric->ury > ury)
	    ury = metric->ury;
	pos += metric->width;
    }

    return Py_BuildValue("iiii", llx, lly, urx, ury);
}

/*
 *	fm.string_width(GIDS[, MAXPOS])
 *
 * Return the setwidth of the glyphs GIDS in 1000-pixel metrics. No
 * kerning or ligatures are taken into account (maybe in the future).
 *
 * If provided, MAXPOS is equivalent to using GIDS[:MAXPOS] instead.
 * MAXPOS defaults to the length. It is useful to compute the position
 * of a caret (See Font.TextCaretData() in font.py)
 */

static PyObject *
skfm_string_width(SKFontMetric * self, PyObject * args)
{
    PyObject * object;
    unsigned int * gids;
    int length, i, maxpos = -1;
    int width = 0;
    SKCharMetric * metric;

    if (!PyArg_ParseTuple(args, "O|i", &object, &maxpos))
	return NULL;
    if (!skfm_get_gids(object, &gids, &length))
	return NULL;

    if (maxpos >= 0 && maxpos < length)
	length = maxpos;

    for (i = 0; i < length; i++)
    {
	metric = skfm_metric_of(self, gids[i]);
	if (metric)
	    width += metric->width;
    }

    return Py_BuildValue("i", width);
}

/*
 *	fm.glyph_width(GID)
 *
 * Return the setwidth of the glyph with id GID (GID is an int).
 * Unknown glyphs have width 0.
 */
static PyObject *
skfm_glyph_width(SKFontMetric * self, PyObject * args)
{
    int gid;

    if (!PyArg_ParseTuple(args, "i", &gid))
	return NULL;

    if (0 <= gid && gid < self->n_metrics)
	return PyInt_FromLong(self->char_metric[gid].width);

    PyErr_SetString(PyExc_ValueError,
		    "argument must be a glyph id of this font");
    return NULL;
}


/*
 *	fm.glyph_bbox(GID)
 *
 * Return the bounding box of the glyph with id GID (GID is an int).
 */
static PyObject *
skfm_glyph_bbox(SKFontMetric * self, PyObject * args)
{
    int gid;

    if (!PyArg_ParseTuple(args, "i", &gid))
	return NULL;

    if (0 <= gid && gid < self->n_metrics)
    {
	SKCharMetric * metric = self->char_metric + gid;
	return Py_BuildValue("iiii", metric->llx, metric->lly,
			     metric->urx, metric->ury);
    }
    PyErr_SetString(PyExc_ValueError,
		    "argument must be a glyph id of this font");
    return NULL;
}

/*
 *	fm.typeset_string(GIDS)
 *
 * Return a list of SKPoint objects, one for each glyph in GIDS,
 * indicating the coordinates of the glyph's origin. The first glyph
 * is set at (0, 0).
 */
static PyObject *
skfm_typeset_string(SKFontMetric * self, PyObject * args)
{
    PyObject * object;
    unsigned int * gids;
    int length, i;
    int width = 0;
    PyObject * list;
    PyObject * point;
    SKCharMetric * metric;

    if (!PyArg_ParseTuple(args, "O", &object))
	return NULL;
    if (!skfm_get_gids(object, &gids, &length))
	return NULL;

    list = PyList_New(length);
    if (!list)
	return NULL;

    for (i = 0; i < length; i++)
    {
	point = SKPoint_FromXY(width / 1000.0, 0.0);
	if (!point)
	{
	    Py_DECREF(list);
	    return NULL;
	}
	if (PyList_SetItem(list, i, point) < 0)
	{
	    Py_DECREF(list);
	    return NULL;
	}
	metric = skfm_metric_of(self, gids[i]);
	if (metric)
	    width += metric->width;
    }

    return list;
}

#define OFF(x) offsetof(SKFontMetric, x)
static struct memberlist skfm_memberlist[] = {
    {"ascender",	T_INT,		OFF(ascender),		RO},
    {"descender",	T_INT,		OFF(descender),		RO},
    {"llx",		T_INT,		OFF(llx),		RO},
    {"lly",		T_INT,		OFF(lly),		RO},
    {"urx",		T_INT,		OFF(urx),		RO},
    {"ury",		T_INT,		OFF(ury),		RO},
    {"italic_angle",	T_FLOAT,	OFF(italic_angle),	RO},
    {NULL} 
};

static struct PyMethodDef skfm_methods[] = {
    {"typeset_string",	(PyCFunction)skfm_typeset_string,	1},
    {"string_bbox",	(PyCFunction)skfm_string_bbox,		1},
    {"string_width",	(PyCFunction)skfm_string_width,		1},
    {"glyph_width",	(PyCFunction)skfm_glyph_width,		1},
    {"glyph_bbox",	(PyCFunction)skfm_glyph_bbox,		1},
    {NULL,	NULL}
};

static PyObject *
skfm_getattr(PyObject * self, char * name)
{
    PyObject * result;

    result = Py_FindMethod(skfm_methods, self, name);
    if (result != NULL)
	return result;
    PyErr_Clear();

    return PyMember_Get((char *)self, skfm_memberlist, name);
}

PyTypeObject SKFontMetricType = {
	PyObject_HEAD_INIT(&PyType_Type)
	0,
	"skfm",
	sizeof(SKFontMetric),
	0,
	(destructor)skfm_dealloc,	/*tp_dealloc*/
	(printfunc)NULL,		/*tp_print*/
	skfm_getattr,			/*tp_getattr*/
	0,				/*tp_setattr*/
	0,				/*tp_compare*/
	0,				/*tp_repr*/
	0,				/*tp_as_number*/
	0,				/*tp_as_sequence*/
	0,				/*tp_as_mapping*/
	0,				/*tp_hash*/
};


/* the module functions */


/*
 *	skfm.CreateMetric(ASCENDER, DESCENDER, FONTBBOX, ITALIC, ENTRIES)
 *
 * Return a new fontmetric object initialized with the given parameters:
 *
 *	ASCENDER	ascender
 *	DESCENDER	descender
 *	FONTBBOX	The font bounding box as a tuple (llx, lly, urx, ury)
 *			in 1000-pixel metrics.
 *	ITALIC		the italic angle in degrees ccw from straight up.
 *	ENTRIES		a sequence of tuples (GID, width, llx, lly, urx,
 *			ury): the glyph id (see devdocs/glyph-text.md) and
 *			the metrics of that glyph in 1000-pixel metrics.
 *			The array is sized to the highest gid and
 *			zero-filled; glyph ids not given have zero
 *			metrics.
 */

PyObject *
SKFM_PyCreateMetric(PyObject * self, PyObject * args)
{
    int ascender, descender;
    PyObject * list;
    SKFontMetric * metric;
    int fllx, flly, furx, fury;
    float italic_angle;
    int i, length, max_gid = -1;

    if (!PyArg_ParseTuple(args, "ii(iiii)fO", &ascender, &descender,
			  &fllx, &flly, &furx, &fury, &italic_angle, &list))
	return NULL;

    if (!PySequence_Check(list))
    {
	PyErr_SetString(PyExc_TypeError,
			"fifth argument must be a sequence of tuples");
	return NULL;
    }

    length = PySequence_Length(list);
    if (length < 1)
    {
	PyErr_SetString(PyExc_ValueError,
			"ENTRIES must have at least one element");
	return NULL;
    }

    metric = (SKFontMetric*)SKFontMetric_New();
    if (!metric)
	return NULL;

    metric->ascender = ascender;
    metric->descender = descender;
    metric->llx = fllx;
    metric->lly = flly;
    metric->urx = furx;
    metric->ury = fury;
    metric->italic_angle = italic_angle;

    /* find the highest glyph id to size the array */
    for (i = 0; i < length; i++)
    {
	int gid, width, llx, lly, urx, ury;
	PyObject * tuple = PySequence_GetItem(list, i);

	if (!PyArg_ParseTuple(tuple, "iiiiii;"
		   "ENTRIES item must be (gid, w, llx, lly, urx, ury)",
			      &gid, &width, &llx, &lly, &urx, &ury))
	{
	    Py_DECREF(tuple);
	    Py_DECREF(metric);
	    return NULL;
	}
	Py_DECREF(tuple);
	if (gid < 0)
	{
	    PyErr_SetString(PyExc_ValueError, "glyph id must be >= 0");
	    Py_DECREF(metric);
	    return NULL;
	}
	if (gid > max_gid)
	    max_gid = gid;
    }

    metric->n_metrics = max_gid + 1;
    metric->char_metric = PyMem_New(SKCharMetric, metric->n_metrics);
    if (!metric->char_metric)
    {
	Py_DECREF(metric);
	return PyErr_NoMemory();
    }
    memset(metric->char_metric, 0,
	   metric->n_metrics * sizeof(SKCharMetric));

    for (i = 0; i < length; i++)
    {
	int gid, width, llx, lly, urx, ury;
	PyObject * tuple = PySequence_GetItem(list, i);
	SKCharMetric * char_metric;

	if (!PyArg_ParseTuple(tuple, "iiiiii;"
		   "ENTRIES item must be (gid, w, llx, lly, urx, ury)",
			      &gid, &width, &llx, &lly, &urx, &ury))
	{
	    Py_DECREF(tuple);
	    Py_DECREF(metric);
	    return NULL;
	}
	Py_DECREF(tuple);
	char_metric = metric->char_metric + gid;
	char_metric->width = width;
	char_metric->llx = llx;
	char_metric->lly = lly;
	char_metric->urx = urx;
	char_metric->ury = ury;
    }

    return (PyObject*) metric;
}

