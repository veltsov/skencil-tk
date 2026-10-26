/*
 *  Copyright (C) 1998, 1999, 2001, 2006 by Bernhard Herzog.
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


#include "filterobj.h"
#include "skmember.h"
#include <structmember.h>

/*
 * Semantics of the methods read, write and close
 * ==============================================
 *
 *
 * size_t write(void *, PyObject * target, const char * buf, size_t length)
 *
 * When the buffer is full and data is written to the filter or when the
 * encode filter is flushed, the buffer data has to be encoded and to be
 * written to the target stream. The filter object will call the write
 * method to achieve this.
 *
 * write is supposed to consume at least 1 byte of the data at buf and
 * at most length bytes. It returns the number of bytes it actually read
 * from buffer.
 *
 * If successful the return value must be at least 1 and at most length.
 * 0 indicates indicates an error, that is, a problem with the
 * underlying data target or an error in the encoder. The filter assumes
 * that a Python exception has been raised.
 *
 *
 *
 * size_t read(void *, PyObject * source, char * buf, size_t length)
 *
 * When the buffer is empty and data is read from the decode filter, the
 * filter calls read to read data from the data source, decode it and
 * store into the buffer.
 *
 * read is supposed to put at least one byte into the buffer beginning
 * at buf and at most length bytes. It returns the number of bytes
 * actually written to buf.
 *
 * If successful, the return value must be at least 1 and at most
 * length. If unsuccessful, a return value of 0 indicates either EOF in
 * the data source or end of data or an error. End of data means that
 * the decoder cannot deliver more data for decoder specific reasons,
 * even if more data is available in the source. The filter assumes that
 * a Python exception has been raised in case of an error.
 *
 * For compatibility, an EOF or EOD (end of data) condition is not
 * converted into an exception.
 *
 *
 * int close(void*, PyObject * target)
 *
 * Called when the filter is being closed. Any data still contained in
 * filter internal state should be written to target. target should not
 * be closed. Return 0 on success and EOF on error (and set an
 * exception).
 */


#define Filter_IsEncoder(filter) ((filter)->write != NULL)
#define Filter_IsDecoder(filter) ((filter)->read != NULL)

#define Filter_CheckEncodeState(filter) \
	(((filter)->flags & (FILTER_CLOSED | FILTER_EOF | FILTER_BAD))\
	 ? setexc(filter) : 1)

#define Filter_CheckDecodeState(filter) \
	(((filter)->flags & (FILTER_CLOSED | FILTER_BAD))\
	 ? setexc(filter) : 1)

static int
setexc(FilterObject * self)
{
    if (self->flags & FILTER_BAD)
    {
	PyErr_Format(PyExc_IOError, "filter %s in bad state",
		     PyUnicode_AsUTF8(self->filtername));
    }
    else if (self->flags & FILTER_CLOSED)
    {
	PyErr_Format(PyExc_IOError, "filter %s already closed",
		     PyUnicode_AsUTF8(self->filtername));
    }
    else if (self->flags & FILTER_EOF)
    {
	PyErr_Format(PyExc_EOFError, "filter %s reached EOF",
		     PyUnicode_AsUTF8(self->filtername));
    }
    return 0;
}

#define FILTER_BUFSIZE (BUFSIZ - 1)

static FilterObject *
new_filter(PyObject * stream, const char * name, int flags,
	   filter_close_proc close, filter_dealloc_proc dealloc,
	   void * client_data)
{
    FilterObject * self;
    
    self = PyObject_New(FilterObject, &FilterType);
    if (!self)
	return NULL;

    self->buffer = PyMem_Malloc(FILTER_BUFSIZE + 1);
    if (!self->buffer)
    {
    error:
	PyObject_Del(self);
	PyErr_NoMemory();
	if (dealloc)
	    dealloc(client_data);
	return NULL;
    }

    self->filtername = PyUnicode_FromString(name);
    if (!self->filtername)
    {
	PyMem_Free(self->buffer);
	goto error;
    }

    self->current = self->base = self->buffer + 1;
    self->buffer_end = self->base + FILTER_BUFSIZE;
    self->end = self->current;

    self->stream = stream;
    Py_INCREF(self->stream);
    self->client_data = client_data;
    self->dealloc = dealloc;
    self->close = close;
    self->write = NULL;
    self->read = NULL;

    self->flags = flags;
    self->streampos = 0;

    return self;
}
    

PyObject *
Filter_NewEncoder(PyObject * target, const char * name, int flags,
		  filter_write_proc write, filter_close_proc close,
		  filter_dealloc_proc dealloc, void * client_data)
{
    FilterObject * self;

    if (!Filter_Check(target) && !PyObject_HasAttrString(target, "write"))
    {
	PyErr_SetString(PyExc_TypeError, "target must be file or filter");
	return NULL;
    }
    
    self = new_filter(target, name, flags, close, dealloc, client_data);
    if (!self)
	return NULL;

    self->write = write;
    self->end = self->buffer_end;
    return (PyObject*)self;
}

PyObject *
Filter_NewDecoder(PyObject * source, const char * name, int flags,
		  filter_read_proc read, filter_close_proc close,
		  filter_dealloc_proc dealloc, void * client_data)
{
    FilterObject * self;

    /*
    if (!PyFile_Check(source) && !Filter_Check(source))
    {
	PyErr_SetString(PyExc_TypeError, "source must be file or filter");
	return NULL;
    }
    */
    
    self = new_filter(source, name, flags, close, dealloc, client_data);
    if (!self)
	return NULL;

    self->read = read;
    self->end = self->current;

    return (PyObject*)self;
}


static void
filter_dealloc(FilterObject * self)
{
    Filter_Close((PyObject*)self);
    if (self->dealloc)
	self->dealloc(self->client_data);
    Py_DECREF(self->filtername);
    Py_DECREF(self->stream);
    PyMem_Free(self->buffer);
    PyObject_Del(self);
}

static PyObject *
filter_repr(FilterObject * self)
{
    char buf[1000];
    PyObject * streamrepr;

    streamrepr = PyObject_Repr(self->stream);
    if (!streamrepr)
	return NULL;

    sprintf(buf, "<filter %.100s %s %.500s>",
	    PyUnicode_AsUTF8(self->filtername),
	    Filter_IsEncoder(self) ? "writing to" : "reading from",
	    PyUnicode_AsUTF8(streamrepr));
    Py_DECREF(streamrepr);
    return PyUnicode_FromString(buf);
}



int
_Filter_Overflow(FilterObject * self, int c)
{
    if (Filter_Flush((PyObject*)self, 1) != EOF)
    {
	*self->current++ = c;
	return c;
    }
    return EOF;
}




static int
_Filter_Uflow(FilterObject * self)
{
    if (Filter_IsDecoder(self))
    {
	size_t result;

	if (!Filter_CheckDecodeState(self) || self->flags & FILTER_EOF)
	    return EOF;

	if (self->current == self->end)
	{
	    result = self->read(self->client_data, self->stream, self->base,
				self->buffer_end - self->base);
	    if (result == 0)
	    {
		if (PyErr_Occurred())
		{
		    self->flags |= FILTER_BAD;
		}
		else
		{
		    self->flags |= FILTER_EOF;
		}
		return EOF;
	    }

	    self->current = self->base;
	    self->end = self->current + result;
	    self->streampos += result;
	}
	return *self->current & 0377;
    }
    return EOF;
}

int
_Filter_Underflow(FilterObject * self)
{
    int c;
    
    c = _Filter_Uflow(self);
    if (c != EOF)
	self->current++;
    return c;
}

int
Filter_Flush(PyObject * filter, int flush_target)
{
    FilterObject * self;
    if (!Filter_Check(filter))
    {
	PyErr_SetString(PyExc_TypeError, "FilterObject expected");
	return EOF;
    }
    
    self = (FilterObject*)filter;
    if (Filter_IsEncoder(self))
    {
	size_t result, length;

	if (!Filter_CheckEncodeState(self))
	    return EOF;

	length = self->current - self->base;
	while (length > 0)
	{
	    result = self->write(self->client_data, self->stream,
				 self->current - length, length);
	    if (result == 0)
	    {
		self->flags |= FILTER_BAD;
		return EOF;
	    }
	    length -= result;
	}

	self->current = self->base;

	/* XXX flush target even if error occurred? */
	if (flush_target)
	{
	    if (!Filter_Check(self->stream))
	    {
		int fflush_result;
		PyObject * res = PyObject_CallMethod(self->stream, "flush", NULL);
		fflush_result = res ? 0 : EOF;
		Py_XDECREF(res);
		if (result < 0)
		{
		    PyErr_SetFromErrno(PyExc_IOError);
		    return EOF;
		}
		return 0;
	    }
	    else if (Filter_Check(self->stream))
		return Filter_Flush(self->stream, flush_target);
	}
	return 0;
    }
    else
    {
	PyErr_SetString(PyExc_TypeError, "flush requires an encode filter");
    }
    return EOF;
}

int
Filter_Close(PyObject * filter)
{
    FilterObject * self;
    int result = 0;
    
    if (!Filter_Check(filter))
    {
	PyErr_SetString(PyExc_TypeError, "FilterObject expected");
	return EOF;
    }

    self = (FilterObject*)filter;

    if (self->flags & FILTER_CLOSED)
	/* filter is already closed, do nothing */
	return 0;
    
    if (Filter_IsEncoder(self) && Filter_Flush((PyObject*)self, 1) < 0)
	return EOF;

    if (self->close)
	result = self->close(self->client_data, self->stream);

    self->flags |= FILTER_CLOSED;
    return result;
}

    

size_t
Filter_Read(PyObject * filter, char * buffer, size_t length)
{
    if (length <= 0)
	return 0;

    if (!Filter_Check(filter))
    {
	/* a python file-like object: use its read() method */
	PyObject * data = PyObject_CallMethod(filter, "read", "n",
					     (Py_ssize_t)length);
	Py_ssize_t size;
	if (!data)
	    return 0;
	if (PyBytes_Check(data))
	{
	    size = PyBytes_GET_SIZE(data);
	    if (size > (Py_ssize_t)length)
		size = length;
	    memcpy(buffer, PyBytes_AS_STRING(data), size);
	}
	else if (PyByteArray_Check(data))
	{
	    size = PyByteArray_GET_SIZE(data);
	    if (size > (Py_ssize_t)length)
		size = length;
	    memcpy(buffer, PyByteArray_AS_STRING(data), size);
	}
	else
	{
	    PyErr_SetString(PyExc_TypeError,
			    "file-like read() must return bytes");
	    size = 0;
	}
	Py_DECREF(data);
	if (size == 0 && PyErr_Occurred())
	    return 0;
	return size;
    }
    else
    {
	size_t to_do = length;
	size_t count;
	char * dest = buffer;
	FilterObject * self = (FilterObject*)filter;

	if (!Filter_CheckDecodeState(self) || self->flags & FILTER_EOF)
	    return 0;

	for (;;)
	{
	    count = self->end - self->current;
	    if (count > to_do)
		count = to_do;
	    if (count > 0)
	    {
		memcpy(dest, self->current, count);
		self->current += count;
		dest += count;
		to_do -= count;
	    }
	    if (to_do == 0 || _Filter_Uflow(self) == EOF)
		break;
	}
	if (PyErr_Occurred())
	    return 0;
	return length - to_do;
    }

    PyErr_SetString(PyExc_TypeError,
		    "filter may be FileObject or FilterObject");
    return 0;
}
		
size_t
Filter_ReadToChar(PyObject * filter, char * buffer, size_t length,
		  int endchar)
{
    if (length <= 0)
	return 0;

    if (Filter_Check(filter))
    {
	FilterObject * self = (FilterObject*)filter;
	int c;
	char * dest = buffer, *end = buffer + length;

	for (;;)
	{
	    c = Filter_GETC(self);
	    if (c == EOF)
		break;
	    *dest++ = c;
	    if (c == endchar || dest == end)
		break;
	}
	if ((c == EOF && dest == buffer) || PyErr_Occurred())
	    return 0;
	return dest - buffer;
    }
    else
    {
	/* a python file-like object: read one byte at a time */
	int c;
	char * dest = buffer, *end = buffer + length;

	for (;;)
	{
	    PyObject * data = PyObject_CallMethod(filter, "read", "n", (Py_ssize_t)1);
	    if (!data)
		return 0;
	    if (data == Py_None || PyObject_Length(data) == 0)
	    {
		Py_DECREF(data);
		break;
	    }
	    *dest++ = *PyBytes_AS_STRING(data);
	    Py_DECREF(data);
	    c = dest[-1];
	    if (c == endchar || dest == end)
		break;
	}
	if (dest == buffer)
	    return 0;
	return dest - buffer;
    }

    PyErr_SetString(PyExc_TypeError,
		    "filter must be FilterObject or FileObject");
    return 0;
}



PyObject *
Filter_GetLine(PyObject * filter, int n)
{
    int n1, n2;
    size_t charsread;
    char * buf, *end, *buffer;
    PyObject *v;

    if (!Filter_Check(filter))
    {
	PyErr_SetString(PyExc_TypeError, "FilterObject expected");
	return NULL;
    }

    n2 = n > 0 ? n : 100;
    buffer = malloc(n2);
    if (buffer == NULL)
	return PyErr_NoMemory();
    buf = buffer;
    end = buffer + n2;

    for (;;)
    {
	charsread = Filter_ReadToChar(filter, buf, n2, '\n');

	if (charsread == 0)
	{
	    if (PyErr_CheckSignals())
	    {
		free(buffer);
		return NULL;
	    }
	    if (n < 0 && buf == buffer) {
		free(buffer);
		PyErr_SetString(PyExc_EOFError, "EOF when reading a line");
		return NULL;
	    }
	    break;
	}
	buf += charsread;
	if (buf[-1] == '\n')
	{
	    if (n < 0)
		buf--;
	    break;
	}
	if (buf == end)
	{
	    if (n > 0)
		break;
	    n1 = n2;
	    n2 += 1000;
	    {
		char * newbuf = realloc(buffer, n2);
		if (!newbuf)
		{
		    free(buffer);
		    return PyErr_NoMemory();
		}
		buffer = newbuf;
	    }
	    buf = buffer + n1;
	    end = buffer + n2;
	}
    }

    n1 = buf - buffer;
    v = PyBytes_FromStringAndSize(buffer, n1);
    free(buffer);
    return v;
}

int Filter_Ungetc(PyObject * filter, int c)
{
    if (Filter_Check(filter))
    {
	FilterObject * self = (FilterObject*)filter;
	if (self->current >= self->base)
	{
	    self->current -= 1;
	    *(self->current) = c;
	}
    }
    else
    {
	PyErr_SetString(PyExc_TypeError, "FilterObject required");
	return -1;
    }
    return 0;
}
    

int
Filter_Write(PyObject * filter, const char * buffer, size_t length)
{
    if (length <= 0)
	return 0;

    if (!Filter_Check(filter))
    {
	/* a python file-like object: use its write() method */
	PyObject * result = PyObject_CallMethod(filter, "write", "y#",
						buffer, (Py_ssize_t)length);
	if (!result)
	    return EOF;
	Py_DECREF(result);
	return length;
    }
    else if (Filter_Check(filter))
    {
	size_t to_do = length;
	size_t count;
	const unsigned char * src = (const unsigned char*)buffer;
	FilterObject * self = (FilterObject*)filter;

	for (;;)
	{
	    count = self->end - self->current;
	    if (count > to_do)
		count = to_do;
	    if (count > 0)
	    {
		memcpy(self->current, src, count);
		self->current += count;
		src += count;
		to_do -= count;
	    }
	    if (to_do == 0 || _Filter_Overflow(self, *src++) == EOF)
		break;
	    to_do -= 1;
	}
	if (to_do != 0 || PyErr_Occurred())
	    return EOF;
	return length - to_do;
    }

    PyErr_SetString(PyExc_TypeError,
		    "filter may be FileObject or FilterObject");
    return EOF;
}



static PyObject *
filter_read(PyObject * self, PyObject * args)
{
    int length;
    size_t read;
    PyObject * string;

    if (!PyArg_ParseTuple(args, "i", &length))
	return NULL;

    char * buffer = malloc(length);
    if (!buffer)
	return PyErr_NoMemory();

    read = Filter_Read(self, buffer, length);
    if (read == 0)
    {
	free(buffer);
	if (PyErr_Occurred())
	    return NULL;
	return PyBytes_FromString("");
    }

    string = PyBytes_FromStringAndSize(buffer, read);
    free(buffer);
    return string;
}


static PyObject *
filter_readline(PyObject * self, PyObject * args)
{
    int length = -1;

    if (!PyArg_ParseTuple(args, "|i", &length))
	return NULL;

    if (length == 0)
	return PyBytes_FromString("");
    if (length < 0)
	length = 0;
    return Filter_GetLine(self, length);
}

#if BUFSIZ < 8192
#define SMALLCHUNK 8192
#else
#define SMALLCHUNK BUFSIZ
#endif

static PyObject *
filter_readlines(PyObject *self, PyObject *args)
{
    long sizehint = 0;
    PyObject *list;
    PyObject *line;
    char small_buffer[SMALLCHUNK];
    char *buffer = small_buffer;
    size_t buffersize = SMALLCHUNK;
    PyObject *big_buffer = NULL;
    size_t nfilled = 0;
    size_t nread;
    size_t totalread = 0;
    char *p, *q, *end;
    int err;

    if (!PyArg_ParseTuple(args, "|l", &sizehint))
	return NULL;
    if ((list = PyList_New(0)) == NULL)
	return NULL;
    for (;;) {
	nread = Filter_Read(self, buffer + nfilled, buffersize - nfilled);
	if (nread == 0) {
	    sizehint = 0;
	    if (!PyErr_Occurred())
		break;
	error:
	    Py_DECREF(list);
	    list = NULL;
	    goto cleanup;
	}
	totalread += nread;
	p = memchr(buffer+nfilled, '\n', nread);
	if (p == NULL) {
	    /* Need a larger buffer to fit this line */
	    nfilled += nread;
	    buffersize *= 2;
	    if (big_buffer == NULL) {
		/* Create the big buffer */
		big_buffer = PyBytes_FromStringAndSize(NULL, buffersize);
		if (big_buffer == NULL)
		    goto error;
		buffer = PyBytes_AS_STRING(big_buffer);
		memcpy(buffer, small_buffer, nfilled);
	    }
	    else {
		/* Grow the big buffer */
		if (PyBytes_Resize(big_buffer, buffersize) < 0)
		    goto error;
		buffer = PyBytes_AS_STRING(big_buffer);
	    }
	    continue;
	}
	end = buffer+nfilled+nread;
	q = buffer;
	do {
	    /* Process complete lines */
	    p++;
	    line = PyBytes_FromStringAndSize(q, p-q);
	    if (line == NULL)
		goto error;
	    err = PyList_Append(list, line);
	    Py_DECREF(line);
	    if (err != 0)
		goto error;
	    q = p;
	    p = memchr(q, '\n', end-q);
	} while (p != NULL);
	/* Move the remaining incomplete line to the start */
	nfilled = end-q;
	memmove(buffer, q, nfilled);
	if (sizehint > 0)
	    if (totalread >= (size_t)sizehint)
		break;
    }
    if (nfilled != 0) {
	/* Partial last line */
	line = PyBytes_FromStringAndSize(buffer, nfilled);
	if (line == NULL)
	    goto error;
	if (sizehint > 0) {
	    /* Need to complete the last line */
	    PyObject *rest = Filter_GetLine(self, 0);
	    if (rest == NULL) {
		Py_DECREF(line);
		goto error;
	    }
	    PyBytes_Concat(&line, rest);
	    Py_DECREF(rest);
	    if (line == NULL)
		goto error;
	}
	err = PyList_Append(list, line);
	Py_DECREF(line);
	if (err != 0)
	    goto error;
    }
 cleanup:
    if (big_buffer) {
	Py_DECREF(big_buffer);
    }
    return list;
}

static PyObject *
filter_write(PyObject * self, PyObject * args)
{
    const char * buffer;
    int length;

    if (!PyArg_ParseTuple(args, "s#", &buffer, &length))
	return NULL;

    if (Filter_Write(self, buffer, length) == EOF)
	return NULL;
    Py_INCREF(Py_None);
    return Py_None;
}
	
static PyObject *
filter_flush(PyObject * self, PyObject * args)
{
    int flush_target = 1;

    if (!PyArg_ParseTuple(args, "|i", &flush_target))
	return NULL;

    if (Filter_Flush(self, flush_target) < 0)
	return NULL;

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
filter_close(PyObject * self, PyObject * args)
{
    if (!PyArg_ParseTuple(args, ""))
	return NULL;

    if (Filter_Close(self) < 0)
	return NULL;

    Py_INCREF(Py_None);
    return Py_None;
}

//#include <stdio.h>
static PyObject *
filter_seek(FilterObject * self, PyObject * args)
{
    int pos;
    long cur_pos, offset;
    
    if (!PyArg_ParseTuple(args, "i", &pos))
	return NULL;

    cur_pos = self->streampos - (self->end - self->current);
    offset = pos - cur_pos;
    //fprintf(stderr,"pos=%d cur_pos=%ld offset=%ld\n",pos,cur_pos,offset);

    if (offset != 0) {

    if (self->base - self->current <= offset
	&& offset < self->end - self->current)
    {
	self->current += offset;
	/* reset the EOF flag if we're not at the end */
	if (self->current < self->end)
	    self->flags &= ~FILTER_EOF;
    }
    else
    {
	PyErr_SetString(PyExc_IOError, "cannot seek to specified position");
	return NULL;
    }
    }
    
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
filter_tell(FilterObject * self, PyObject * args)
{
    long cur_pos;
    
    if (!PyArg_ParseTuple(args, ""))
	return NULL;

    cur_pos = self->streampos - (self->end - self->current);
    return PyLong_FromLong(cur_pos);
}

#define OFF(x) offsetof(FilterObject, x)
static SKMemberDef filter_memberlist[] = {
    {"stream",		T_OBJECT,	OFF(stream),	RO},
    {"source",		T_OBJECT,	OFF(stream),	RO},
    {"target",		T_OBJECT,	OFF(stream),	RO},
    {NULL}
};

static struct PyMethodDef filter_methods[] = {
    {"read",		(PyCFunction)filter_read,		1},
    {"write",		(PyCFunction)filter_write,		1},
    {"readline",	(PyCFunction)filter_readline,		1},
    {"readlines",	(PyCFunction)filter_readlines,		1},
    {"flush",		(PyCFunction)filter_flush,		1},
    {"seek",		(PyCFunction)filter_seek,		1},
    {"tell",		(PyCFunction)filter_tell,		1},
    {"close",		(PyCFunction)filter_close,		1},
    {NULL,	NULL}
};

static PyObject *
filter_getattr(PyObject * self, char * name)
{
    PyObject * result;

    result = SK_FindMethod(filter_methods, self, name);
    if (result != NULL)
	return result;
    PyErr_Clear();

    return SKMember_Get((char *)self, filter_memberlist, name);
}



static int
filter_setattr(PyObject * self, char * name, PyObject * v)
{
    if (v == NULL) {
	PyErr_SetString(PyExc_AttributeError,
			"can't delete object attributes");
	return -1;
    }
    return SKMember_Set((char *)self, filter_memberlist, name, v);
}


PyTypeObject FilterType = {
	PyObject_HEAD_INIT(&PyType_Type)
	0,
	"filter",
	sizeof(FilterObject),
	0,
	(destructor)filter_dealloc,	/*tp_dealloc*/
	(printfunc)0,			/*tp_print*/
	filter_getattr,			/*tp_getattr*/
	filter_setattr,			/*tp_setattr*/
	0,				/*tp_as_async*/
	(reprfunc)filter_repr,		/*tp_repr*/
	0,				/*tp_as_number*/
	0,				/*tp_as_sequence*/
	0,				/*tp_as_mapping*/
	0,				/*tp_hash*/
	0,				/*tp_call*/
	0,				/*tp_str*/
	0,				/*tp_getattro*/
	0,				/*tp_setattro*/
	0,				/*tp_as_buffer*/
	Py_TPFLAGS_DEFAULT,		/*tp_flags*/
};


