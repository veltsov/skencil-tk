#define PY_SSIZE_T_CLEAN
/*
 *  Copyright (C) 1998, 1999 by Bernhard Herzog.
 *
 *			All Rights Reserved
 *
 *  Permission to use, copy, modify, and distribute this software and
 *  its documentation for any purpose and without fee is hereby granted,
 *  provided that the above copyright notice appear in all copies and
 *  that both that copyright notice and this permission notice appear in
 *  supporting documentation, and that the name of the author not be
 *  used in advertising or publicity pertaining to distribution of the
 *  software without specific, written prior permission.
 *
 *  THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
 *  INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN
 *  NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, INDIRECT OR
 *  CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
 *  OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
 *  NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION
 *  WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */

#include "stringfilter.h"

#define FBUFLEN 1024

typedef struct {
    PyObject * string;
    char * pos;
    size_t left;
} StringDecodeState;


static size_t
read_string(void* clientdata, PyObject * source, char * buf, size_t length)
{
    StringDecodeState * state = (StringDecodeState*)clientdata;
    size_t copy;
    
    if (state->left > 0)
    {
	if (state->left > length)
	    copy = length;
	else
	    copy = state->left;
	memcpy(buf, state->pos, copy);
	state->left -= copy;
	state->pos += copy;
    }
    else if (source != Py_None)
    {
	copy = Filter_Read(source, buf, length);
    }
    else
    {
	copy = 0;
    }
    return copy;
}


static void
string_state_dealloc(void * clientdata)
{
    Py_DECREF(((StringDecodeState*)clientdata)->string);
    free(clientdata);
}

PyObject *
Filter_StringDecode(PyObject * self, PyObject * args)
{
    PyObject * source;
    PyObject * string;
    StringDecodeState * state;

    if (!PyArg_ParseTuple(args, "OO", &string, &source))
	return NULL;

    state = malloc(sizeof (StringDecodeState));
    if (!state)
	return PyErr_NoMemory();
    state->string = string;
    Py_INCREF(state->string);
    if (PyUnicode_Check(string))
    {
	Py_ssize_t size;
	state->pos = (char*)PyUnicode_AsUTF8AndSize(string, &size);
	state->left = size;
    }
    else if (PyBytes_Check(string))
    {
	state->pos = PyBytes_AsString(string);
	state->left = PyBytes_Size(string);
    }
    else
    {
	free(state);
	PyErr_SetString(PyExc_TypeError,
			"expected a str or bytes string");
	return NULL;
    }

    return Filter_NewDecoder(source, "StringDecode", 0, read_string, NULL,
			     string_state_dealloc, state);
}
