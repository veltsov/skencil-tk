#ifndef SKMEMBER_H
#define SKMEMBER_H

#include <string.h>
#include <structmember.h>

/* RO was removed from Python 3's structmember.h */
#ifndef RO
#define RO READONLY
#endif

/* Replacement for the PyMember_Get/PyMember_Set/struct memberlist API
 * that was removed in Python 3.  Supports the member kinds this code
 * base uses (see the *_memberlist tables). */

typedef struct {
    char *name;
    int type;
    Py_ssize_t offset;
    int flags;
} SKMemberDef;

static PyObject *
SKMember_Get(char *addr, SKMemberDef *mlist, char *name)
{
    SKMemberDef *m;
    for (m = mlist; m->name != NULL; m++)
    {
	if (strcmp(m->name, name) == 0)
	{
	    char *member_addr = addr + m->offset;
	    switch (m->type)
	    {
	    case T_INT:
		return PyLong_FromLong(*(int*)member_addr);
	    case T_ULONG:
		return PyLong_FromUnsignedLong(*(unsigned long*)member_addr);
	    case T_FLOAT:
		return PyFloat_FromDouble(*(float*)member_addr);
	    case T_DOUBLE:
		return PyFloat_FromDouble(*(double*)member_addr);
	    case T_BYTE:
		return PyLong_FromLong(*(char*)member_addr);
	    case T_OBJECT:
	    {
		PyObject *value = *(PyObject**)member_addr;
		if (!value)
		    value = Py_None;
		Py_INCREF(value);
		return value;
	    }
	    }
	}
    }
    PyErr_SetString(PyExc_AttributeError, name);
    return NULL;
}

static int
SKMember_Set(char *addr, SKMemberDef *mlist, char *name, PyObject *v)
{
    SKMemberDef *m;
    for (m = mlist; m->name != NULL; m++)
    {
	if (strcmp(m->name, name) == 0)
	{
	    char *member_addr = addr + m->offset;
	    if (m->flags & RO)
	    {
		PyErr_SetString(PyExc_TypeError, "readonly attribute");
		return -1;
	    }
	    switch (m->type)
	    {
	    case T_BYTE:
	    {
		long value = PyLong_AsLong(v);
		if (value == -1 && PyErr_Occurred())
		    return -1;
		*(char*)member_addr = (char)value;
		return 0;
	    }
	    case T_OBJECT:
	    {
		PyObject *old = *(PyObject**)member_addr;
		Py_INCREF(v);
		*(PyObject**)member_addr = v;
		Py_XDECREF(old);
		return 0;
	    }
	    }
	    break;
	}
    }
    PyErr_SetString(PyExc_AttributeError, name);
    return -1;
}

/* Convert the result of one of the old tp_compare functions into a
 * rich-comparison result for tp_richcompare. */
static PyObject *
SK_RichCompare(int result, int op)
{
    switch (op)
    {
    case Py_EQ: return PyBool_FromLong(result == 0);
    case Py_NE: return PyBool_FromLong(result != 0);
    case Py_LT: return PyBool_FromLong(result < 0);
    case Py_LE: return PyBool_FromLong(result <= 0);
    case Py_GT: return PyBool_FromLong(result > 0);
    case Py_GE: return PyBool_FromLong(result >= 0);
    }
    Py_RETURN_NOTIMPLEMENTED;
}

/* Replacement for Py_FindMethod (removed in Python 3).  Like the old
 * function it raises AttributeError when the name is not found. */
static PyObject *
SK_FindMethod(PyMethodDef *methods, PyObject * self, char * name)
{
    PyMethodDef * def;
    for (def = methods; def->ml_name != NULL; def++)
    {
	if (strcmp(def->ml_name, name) == 0)
	    return PyCFunction_New(def, self);
    }
    PyErr_SetString(PyExc_AttributeError, name);
    return NULL;
}

#endif /* SKMEMBER_H */