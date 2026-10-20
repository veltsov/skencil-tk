#include <stdio.h>
#include <string.h>

#include <Python.h>

/* Starting with Tcl 8.4, many APIs offer const-correctness.
   Unfortunately, making _tkinter correct for this API means to break
   earlier versions. USE_COMPAT_CONST allows to make Pax work with both
   8.4 and earlier versions. Once Tcl releases before 8.4 don't need to
   be supported anymore, this should go. */
#define USE_COMPAT_CONST

#include <tcl.h>
#include <tk.h>

#include <X11/Xutil.h>

#include "tkwinobject.h"
#include "regionobject.h"
#include "pixmapobject.h"
#include "borderobject.h"

#include "clipmask.h"

#include "paxmodule.h"

/* only for the type objects: */
#include "cmapobject.h"
#include "fontobject.h"
#include "imageobject.h"
#include "gcobject.h"

typedef enum {
    MapMethodIdx,
    DestroyMethodIdx,
    RedrawMethodIdx,
    InitTkWinObjectIdx,
    InitTkBorderIdx,
    ScrollXMoveIdx,
    ScrollXUnitsIdx,
    ScrollXPagesIdx,
    ScrollYMoveIdx,
    ScrollYUnitsIdx,
    ScrollYPagesIdx,
    ResizedMethodIdx,
    ExtensionEventIdx,
    NUM_METHOD_NAMES
} MethodIndex;

static char * method_names[NUM_METHOD_NAMES] = {
    "MapMethod",
    "DestroyMethod",
    "RedrawMethod",
    "InitTkWinObject",
    "InitTkBorder",
    "ScrollXMove",
    "ScrollXUnits",
    "ScrollXPages",
    "ScrollYMove",
    "ScrollYUnits",
    "ScrollYPages",
    "ResizedMethod",
    "ExtensionEvent"
};

static PyObject * object_registry = NULL;

static PyObject * method_names_obj[NUM_METHOD_NAMES];

static void
print_failure_message(char * msg)
{
    if (PyErr_Occurred() != PyExc_SystemExit)
    {
	fputs(msg, stderr); putc('\n', stderr);
	PyErr_Print(); PyErr_Clear();
	fprintf(stderr, "---\n");
    }
}


static int
paxWidget_CallMethodArgs(PyObject * obj, int method_idx, PyObject * args)
{
    PyObject * result;
    PyObject * method;
    PyGILState_STATE gilstate;

    if (obj == NULL)
	return 0;

    if (args == NULL)
	return -1;

    /* Stock _tkinter releases the GIL around every Tcl call and event
       dispatch. This function may be invoked from such a context (via
       paxwidget_cmd, PaxWidgetEventProc, PaxWidgetDisplay), so make
       sure the GIL is held while calling Python. */
    gilstate = PyGILState_Ensure();

    method = PyObject_GetAttr(obj, method_names_obj[method_idx]);
    if (!method)
    {
	/* do nothing if the object doesn't have the method */
	fprintf(stderr, "No Method %s\n",
		PyString_AsString(method_names_obj[method_idx]));
	PyErr_Clear();
	PyGILState_Release(gilstate);
	return 0;
    }

    result = PyObject_CallObject(method, args);

    Py_DECREF(method);
    Py_DECREF(args);
    if (result == NULL)
    {
	char buf[100];
	sprintf(buf, "--- Calling %.40s failed---", method_names[method_idx]);
	print_failure_message(buf);
	PyGILState_Release(gilstate);
	return 0;
    }
    Py_DECREF(result);
    PyGILState_Release(gilstate);
    return 0;
}

/* ugly: there should be a standard way to access Tk internals from a
   python module outside of _tkinter */
typedef struct
{
    PyObject_HEAD
    Tcl_Interp *interp;
}
TkappObject;



typedef struct PaxWidget_s{
    Tk_Window	tkwin;
    Tcl_Interp *interp;
    Tcl_Command widget_cmd;
    Display *	display;
    int		update_pending;
    Region	exposed_region;
    PyObject *	obj;
    Tk_3DBorder	background;
    int		background_inited;
    Cursor	cursor;
    char *	class_name;
    int width;			/* Width to request for window.	 <= 0 means
				 * don't request any size. */
    int height;			/* Height to request for window. */
} PaxWidget;

/* Marshall a method call on the widget's Python object through the
   'call_py_method' Tcl command, which is registered via _tkinter's
   createcommand (PythonCmd). _tkinter then handles the GIL and its
   internal tcl_tstate bookkeeping correctly, also when the called
   Python method makes nested tk calls.

   This function may be called with the GIL released (from Tcl event
   dispatch), so it must not use the Python C API directly.
*/
static void
paxWidget_EvalMethod(PaxWidget * paxwidget, int method_idx, const char * args)
{
    char cmd[256];

    if (paxwidget->obj == NULL)
	return;

    if (args)
	sprintf(cmd, "call_py_method %ld %s %s",
		(long) paxwidget->obj, method_names[method_idx], args);
    else
	sprintf(cmd, "call_py_method %ld %s",
		(long) paxwidget->obj, method_names[method_idx]);

    if (Tcl_Eval(paxwidget->interp, cmd) != TCL_OK)
	fprintf(stderr, "pax: %s\n", Tcl_GetStringResult(paxwidget->interp));
}


static int tk_pyobject_parse(ClientData clientData,
			     Tcl_Interp *interp,
			     Tk_Window tkwin,
			     char *value,
			     char *widgRec,
			     int offset)
{
    PyObject * obj;
    if (!object_registry)
    {
    Tcl_SetResult(interp, "object_registry not initialized", TCL_VOLATILE);
	return TCL_ERROR;
    }
    obj = PyDict_GetItemString(object_registry, value);
    if (!obj)
    {
    Tcl_SetResult(interp, "object not in registry", TCL_VOLATILE);
	return TCL_ERROR;
    }

    Py_INCREF(obj);
    Py_XDECREF((*((PyObject**)(widgRec + offset))));
    *((PyObject**)(widgRec + offset)) = obj;

    return TCL_OK;
}

static char *
tk_pyobject_print(ClientData clientData, Tk_Window tkwin, char *widgRec,
		  int offset, Tcl_FreeProc **freeProcPtr)
{
    static char buf[100];
    sprintf(buf, "%ld", (long)*((PyObject**)(widgRec + offset)));
    return buf;
}



Tk_CustomOption tk_PyObject_option = {
    tk_pyobject_parse,
    tk_pyobject_print,
    NULL
};

static Tk_ConfigSpec configSpecs[] = {
    
#define CFGIDX_OBJECT	0
    {TK_CONFIG_CUSTOM, "-pyobject", "", "",
     "", Tk_Offset(PaxWidget, obj), TK_CONFIG_DONT_SET_DEFAULT,
     &tk_PyObject_option},
    
#define CFGIDX_HEIGHT	1
    {TK_CONFIG_PIXELS, "-height", "height", "Height",
     "0", Tk_Offset(PaxWidget, height), 0},
    
#define CFGIDX_WIDTH	2
    {TK_CONFIG_PIXELS, "-width", "width", "Width",
     "0", Tk_Offset(PaxWidget, width), 0},
    
#define CFGIDX_BACKGROUND 3
    {TK_CONFIG_BORDER, "-background", "background", "Background",
     "#d9d9d9", Tk_Offset(PaxWidget, background), 0},
    
#define CFGIDX_CURSOR	4
    {TK_CONFIG_ACTIVE_CURSOR, "-cursor", "cursor", "Cursor",
     "", Tk_Offset(PaxWidget, cursor), TK_CONFIG_NULL_OK},
    
#define CFGIDX_CLASS	5
    {TK_CONFIG_STRING, "-class", "class", "Class",
     "", Tk_Offset(PaxWidget, class_name), TK_CONFIG_NULL_OK},
    
    {TK_CONFIG_END, (char *) NULL, (char *) NULL, (char *) NULL,
	(char *) NULL, 0, 0}
};



static int PaxWidgetConfigure(Tcl_Interp * interp, PaxWidget * paxwidget,
			     int argc, char**argv, int flags);
static void PaxWidgetEventProc (ClientData clientData, XEvent *eventPtr);

static int paxwidget_widget_cmd(ClientData data, Tcl_Interp * interp,
			       int argc, char** argv);
static void PaxWidgetDisplay(ClientData clientData);
static void PaxWidgetDestroy(char * data);

/* Stock _tkinter releases the GIL around Tcl calls; this Tcl command is
   invoked from such a context, so acquire the GIL for the whole body. */
static int
paxwidget_cmd_impl(ClientData data, Tcl_Interp * interp, int argc, char** argv)
{
    Tk_Window tkmain = (Tk_Window) data;
    Tk_Window tkwin;
    PaxWidget * paxwidget;
    char * class_name = NULL;
    int i;

    if (argc < 2)
    {
	Tcl_AppendResult(interp, "wrong # args: should be \"",
			 argv[0], " pathName ?options?\"", (char *) NULL);
	return TCL_ERROR;
    }

    /* look for the -class option */
    for (i = 2; i < argc; i += 2)
    {
	int length;
	char c;
	char * arg;
	
	arg = argv[i];
	length = strlen(arg);
	if (length < 2)
	    continue;
	c = arg[1];
	if ((c == 'c') && (strncmp(arg, "-class", strlen(arg)) == 0)
	    && (length >= 3))
	{
	    if (i < argc - 1)
		class_name = argv[i+1];
	    else
		fprintf(stderr,
			"No argument for -class option, using defaults");
	}
    }

    tkwin = Tk_CreateWindowFromPath(interp, tkmain, argv[1], (char*)NULL);
    if (tkwin == NULL)
    {
	return TCL_ERROR;
    }
    if (class_name)
	Tk_SetClass(tkwin, class_name);
    else
	Tk_SetClass(tkwin, "PaxWidget");

    paxwidget = (PaxWidget*) ckalloc(sizeof(PaxWidget));
    if (!paxwidget)
	return TCL_ERROR;
    paxwidget->tkwin = tkwin;
    paxwidget->display = Tk_Display(tkwin);
    paxwidget->interp = interp;
    paxwidget->widget_cmd = Tcl_CreateCommand(interp, Tk_PathName(tkwin),
					      paxwidget_widget_cmd,
					      (ClientData) paxwidget, NULL);
    paxwidget->obj = NULL;
    paxwidget->width = paxwidget->height = 0;
    paxwidget->background = NULL;
    paxwidget->background_inited = 0;
    paxwidget->cursor = None;
    paxwidget->class_name = NULL;
    paxwidget->update_pending = 0;
    paxwidget->exposed_region = XCreateRegion();


    Tk_CreateEventHandler(paxwidget->tkwin, ExposureMask|StructureNotifyMask,
			  PaxWidgetEventProc, (ClientData) paxwidget);

    if (PaxWidgetConfigure(interp, paxwidget, argc - 2, argv + 2, 0) != TCL_OK)
    {
	Tk_DestroyWindow(paxwidget->tkwin);
	return TCL_ERROR;
    }

    Tcl_SetResult(interp, Tk_PathName(paxwidget->tkwin), TCL_VOLATILE);
    return TCL_OK;
}

static int
paxwidget_cmd(ClientData data, Tcl_Interp * interp, int argc, char** argv)
{
    int result;
    PyGILState_STATE gilstate = PyGILState_Ensure();
    result = paxwidget_cmd_impl(data, interp, argc, argv);
    PyGILState_Release(gilstate);
    return result;
}

static void
PaxWidgetDestroy_impl(char * data)
{
    PaxWidget *paxwidget = (PaxWidget *) data;

    Tk_FreeOptions(configSpecs, (char *) paxwidget, paxwidget->display, 0);
    Py_XDECREF(paxwidget->obj);
    XDestroyRegion(paxwidget->exposed_region);
    ckfree((char *) paxwidget);
}

/* may be called (indirectly via Tk_EventuallyFree) without the GIL */
static void
PaxWidgetDestroy(char * data)
{
    PyGILState_STATE gilstate = PyGILState_Ensure();
    PaxWidgetDestroy_impl(data);
    PyGILState_Release(gilstate);
}


static void
PaxWidget_RegisterUpdate(PaxWidget * paxwidget)
{
    if (!paxwidget->update_pending)
    {
	Tk_DoWhenIdle(PaxWidgetDisplay, (ClientData) paxwidget);
	paxwidget->update_pending = 1;
    }
}

static int
PaxWidgetConfigure(Tcl_Interp * interp, PaxWidget * paxwidget,
		   int argc, char**argv, int flags)
{
    if (Tk_ConfigureWidget(interp, paxwidget->tkwin, configSpecs, argc, argv,
			   (char*) paxwidget, flags) != TCL_OK)
	return TCL_ERROR;

    if ((configSpecs[CFGIDX_OBJECT].specFlags & TK_CONFIG_OPTION_SPECIFIED)
	!= 0)
    {
	PyObject * tkwin = TkWin_FromTkWindow(paxwidget->interp,
					      paxwidget->tkwin);
	if (!tkwin)
	{
	    print_failure_message("Cannot initialize tkwin object");
	    return TCL_ERROR;
	}
	paxWidget_CallMethodArgs(paxwidget->obj, InitTkWinObjectIdx,
				 Py_BuildValue("(O)", tkwin));
	Py_DECREF(tkwin);
    }

    if (paxwidget->width > 0 || paxwidget->height > 0)
    {
	Tk_GeometryRequest(paxwidget->tkwin, paxwidget->width,
			   paxwidget->height);
    }

    if (!paxwidget->background_inited
	|| (configSpecs[CFGIDX_BACKGROUND].specFlags
	    & TK_CONFIG_OPTION_SPECIFIED) != 0)
    {
	PyObject * border = PaxBorder_FromTkBorder(paxwidget->background,
						  paxwidget->tkwin, 1);
	if (!border)
	{
	    print_failure_message("Cannot initialize tkborder objects");
	    return TCL_ERROR;
	}
	paxWidget_CallMethodArgs(paxwidget->obj, InitTkBorderIdx,
				 Py_BuildValue("(O)", border));
	Py_DECREF(border);
	paxwidget->background_inited = 1;
	Tk_SetBackgroundFromBorder(paxwidget->tkwin, paxwidget->background);
    }

    return TCL_OK;
}


/* may be invoked from Tcl event dispatch without the GIL */
static int
paxwidget_widget_cmd_impl(ClientData data, Tcl_Interp * interp,
		     int argc, char** argv)
{
    PaxWidget * paxwidget = (PaxWidget*)data;
    int result = TCL_OK;
    size_t length;
    char c;

    if (argc < 2)
    {
	Tcl_AppendResult(interp, "wrong # args: should be \"",
			 argv[0], " option ?arg arg ...?\"", (char *) NULL);
	return TCL_ERROR;
    }
    Tk_Preserve((ClientData) paxwidget);
    c = argv[1][0];
    length = strlen(argv[1]);
    if (c == 'b' && strncmp(argv[1], "bgpixel", length) == 0)
    {
      Tcl_SetObjResult(interp, Tcl_NewLongObj(
		       Tk_3DBorderColor(paxwidget->background)->pixel));
    }
    else if ((c == 'c') && (strncmp(argv[1], "cget", length) == 0)
	     && (length >= 2))
    {
	if (argc != 3)
	{
	    Tcl_AppendResult(interp, "wrong # args: should be \"",
			     argv[0], " cget option\"",
			     (char *) NULL);
	    goto error;
	}
	result = Tk_ConfigureValue(interp, paxwidget->tkwin, configSpecs,
				   (char *) paxwidget, argv[2], 0);
    }
    else if ((c == 'c') && (strncmp(argv[1], "configure", length) == 0)
	     && (length >= 2))
    {
	if (argc == 2)
	{
	    result = Tk_ConfigureInfo(interp, paxwidget->tkwin, configSpecs,
				      (char *) paxwidget, (char *) NULL, 0);
	}
	else if (argc == 3)
	{
	    result = Tk_ConfigureInfo(interp, paxwidget->tkwin, configSpecs,
				      (char *) paxwidget, argv[2], 0);
	}
	else
	{
	    result = PaxWidgetConfigure(interp, paxwidget, argc-2, argv+2,
					TK_CONFIG_ARGV_ONLY);
	}
    }
    else if ((c == 'm') && (strncmp(argv[1], "motionhints", length) == 0))
    {
	XSetWindowAttributes* attr;
	if (argc != 2)
	{
	    Tcl_AppendResult(interp, "wrong # args: should be \"",
			     argv[0], " motionhints\"",
			     (char *) NULL);
	    goto error;
	}

	attr = Tk_Attributes(paxwidget->tkwin);
	XSelectInput(Tk_Display(paxwidget->tkwin),
		     Tk_WindowId(paxwidget->tkwin),
		     attr->event_mask | PointerMotionHintMask);

    }
    else if ((c == 'u') && (strncmp(argv[1], "update", length) == 0))
    {
	if (argc != 2)
	{
	    Tcl_AppendResult(interp, "wrong # args: should be \"",
			     argv[0], " update\"",
			     (char *) NULL);
	    goto error;
	}
	PaxWidget_RegisterUpdate(paxwidget);
    }
    else if ((c == 'x') && (strncmp(argv[1], "xview", length) == 0))
    {
	int count, type;
	double fraction;

	type = Tk_GetScrollInfo(interp, argc, argv, &fraction, &count);

	switch (type)
	{
	case TK_SCROLL_ERROR:
	    goto error;
	case TK_SCROLL_MOVETO:
	    paxWidget_CallMethodArgs(paxwidget->obj, ScrollXMoveIdx,
				     Py_BuildValue("(d)", fraction));
	    break;
	case TK_SCROLL_PAGES:
	    paxWidget_CallMethodArgs(paxwidget->obj, ScrollXPagesIdx,
				     Py_BuildValue("(i)", count));
	    break;
	case TK_SCROLL_UNITS:
	    paxWidget_CallMethodArgs(paxwidget->obj, ScrollXUnitsIdx,
				     Py_BuildValue("(i)", count));
	    break;
	}
    }
    else if ((c == 'y') && (strncmp(argv[1], "yview", length) == 0))
    {
	int count, type;
	double fraction;

	type = Tk_GetScrollInfo(interp, argc, argv, &fraction, &count);

	switch (type)
	{
	case TK_SCROLL_ERROR:
	    goto error;
	case TK_SCROLL_MOVETO:
	    paxWidget_CallMethodArgs(paxwidget->obj, ScrollYMoveIdx,
				     Py_BuildValue("(d)", fraction));
	    break;
	case TK_SCROLL_PAGES:
	    paxWidget_CallMethodArgs(paxwidget->obj, ScrollYPagesIdx,
				     Py_BuildValue("(i)", count));
	    break;
	case TK_SCROLL_UNITS:
	    paxWidget_CallMethodArgs(paxwidget->obj, ScrollYUnitsIdx,
				     Py_BuildValue("(i)", count));
	    break;
	}
    }

    Tk_Release((ClientData) paxwidget);
    return result;

 error:
    Tk_Release((ClientData) paxwidget);
    return TCL_ERROR;
}

static void
handle_expose_event(PaxWidget * paxwidget, XEvent * event)
{
    XRectangle rect;
    if (paxwidget->exposed_region == None)
	paxwidget->exposed_region = XCreateRegion();
    rect.x = event->xexpose.x;
    rect.y = event->xexpose.y;
    rect.width = event->xexpose.width;
    rect.height = event->xexpose.height;
    XUnionRectWithRegion(&rect, paxwidget->exposed_region,
			 paxwidget->exposed_region);
    PaxWidget_RegisterUpdate(paxwidget);
}

/* may be invoked from Tcl event dispatch without the GIL */
static int
paxwidget_widget_cmd(ClientData data, Tcl_Interp * interp,
		     int argc, char** argv)
{
    int result;
    PyGILState_STATE gilstate = PyGILState_Ensure();
    result = paxwidget_widget_cmd_impl(data, interp, argc, argv);
    PyGILState_Release(gilstate);
    return result;
}


/* may be invoked from Tcl event dispatch without the GIL; all Python
   callbacks are marshaled through the call_py_method Tcl command (see
   paxWidget_EvalMethod), so no direct Python C API calls here */
static void
PaxWidgetEventProc(ClientData clientData, XEvent *event)
{
    PaxWidget *paxwidget = (PaxWidget *) clientData;

    if (event->type == Expose || event->type == GraphicsExpose)
    {
	handle_expose_event(paxwidget, event);
    }
    else if (event->type == ConfigureNotify)
    {
	char args[40];
	sprintf(args, "%d %d", event->xconfigure.width,
		event->xconfigure.height);
	paxWidget_EvalMethod(paxwidget, ResizedMethodIdx, args);
    }
    else if (event->type == MapNotify)
    {
	paxWidget_EvalMethod(paxwidget, MapMethodIdx, NULL);
    }
    else if (event->type == DestroyNotify)
    {
	paxWidget_EvalMethod(paxwidget, DestroyMethodIdx, NULL);

	if (paxwidget->tkwin != NULL)
	{
	    paxwidget->tkwin = NULL;
	    Tcl_DeleteCommand(paxwidget->interp,
			      Tcl_GetCommandName(paxwidget->interp,
						 paxwidget->widget_cmd));
	}
	if (paxwidget->update_pending)
	{
	    Tk_CancelIdleCall(PaxWidgetDisplay, (ClientData) paxwidget);
	}
	Tk_EventuallyFree((ClientData) paxwidget, PaxWidgetDestroy);
    }
    else if (event->type > LASTEvent)
    {
	char args[20];
	sprintf(args, "%d", event->type);
	paxWidget_EvalMethod(paxwidget, ExtensionEventIdx, args);
    }
}

/* may be invoked (via Tk_DoWhenIdle) without the GIL; the exposed
   region is handed over to the Python side as a pointer marshaled
   through the call_py_method Tcl command */
static void
PaxWidgetDisplay(ClientData clientData)
{
    PaxWidget *paxwidget = (PaxWidget *) clientData;
    Tk_Window tkwin = paxwidget->tkwin;
    char args[32];

    paxwidget->update_pending = 0;
    if (!Tk_IsMapped(tkwin))
	return;

    sprintf(args, "%lu", (unsigned long) paxwidget->exposed_region);
    paxwidget->exposed_region = XCreateRegion();

    paxWidget_EvalMethod(paxwidget, RedrawMethodIdx, args);
}


/*
 *	Python	module stuff
 */

static PyObject *
name_to_window(PyObject * self, PyObject * args)
{
    PyObject * app_or_interpaddr;
    Tcl_Interp * interp;
    Tk_Window	tkwin;
    char * name;
    
    if (!PyArg_ParseTuple(args, "sO", &name, &app_or_interpaddr))
	return NULL;

    if (PyInt_Check(app_or_interpaddr))
    {
	interp = (Tcl_Interp*)PyInt_AsLong(app_or_interpaddr);
    }
    else
    {
	interp = ((TkappObject*)app_or_interpaddr)->interp;
    }

    tkwin = Tk_NameToWindow(interp, name, (ClientData)Tk_MainWindow(interp));
    if (!tkwin)
    {
	PyErr_SetString(PyExc_ValueError, Tcl_GetStringResult(interp));
	return NULL;
    }

    return TkWin_FromTkWindow(interp, tkwin);
}

static PyObject *
do_one_event(PyObject * self, PyObject * args)
{
    int flags;

    if (!PyArg_ParseTuple(args, "i", &flags))
	return NULL;

    return PyInt_FromLong(Tcl_DoOneEvent(flags));
}

static PyObject *
key_for_object(PyObject *obj)
{
    char id[20];
    sprintf(id, "%ld", (long)obj);
    return PyString_FromString(id);
}

static PyObject *
register_object(PyObject * self, PyObject * args)
{
    PyObject * obj, *key;
    int result;

    if (!PyArg_ParseTuple(args, "O", &obj))
	return NULL;

    if (!object_registry)
    {
	object_registry = PyDict_New();
	if (!object_registry)
	    return NULL;
    }

    key = key_for_object(obj);
    result = PyDict_SetItem(object_registry, key, obj);

    if (result < 0)
    {
	Py_DECREF(key);
	return NULL;
    }

    return key;
}

static PyObject *
unregister_object(PyObject * self, PyObject * args)
{
    PyObject * obj;
    int result;

    if (!PyArg_ParseTuple(args, "O", &obj))
	return NULL;

    if (object_registry)
    {
	PyObject *key = key_for_object(obj);
	result = PyDict_DelItem(object_registry, key);
	if (result < 0)
	    PyErr_Clear();
	Py_DECREF(key);
    }
    Py_INCREF(Py_None);
    return Py_None;
}


/* The 'call_py_method' command is registered via _tkinter's
   createcommand (see create_tcl_commands below), so that it is
   dispatched by _tkinter's PythonCmd: that guarantees the GIL is held
   and _tkinter's internal tcl_tstate bookkeeping stays correct, also
   when the called method makes nested tk calls. (A raw
   Tcl_CreateCommand would be invoked with the GIL released by stock
   _tkinter, and PyGILState_Ensure/Release around the body cannot
   restore tcl_tstate afterwards.)

   Called with (key, methodname, arg...); all arguments arrive as
   strings (both from MakeMethodCommand scripts and from the event
   marshaling in paxWidget_EvalMethod). The arguments of the
   event-driven methods are converted back to their original types
   here. */
static PyObject *
pax_call_py_method(PyObject * self, PyObject * args)
{
    PyObject * obj, *method, *call_args, *result;
    char * key, *name;
    Py_ssize_t argc = PyTuple_GET_SIZE(args);
    int i;

    if (argc < 2)
    {
	PyErr_SetString(PyExc_TypeError,
			"call_py_method requires key and method name");
	return NULL;
    }
    key = PyString_AsString(PyTuple_GET_ITEM(args, 0));
    name = PyString_AsString(PyTuple_GET_ITEM(args, 1));
    if (!key || !name)
	return NULL;

    if (!object_registry)
	Py_RETURN_NONE;

    obj = PyDict_GetItemString(object_registry, key);
    if (!obj)
    {
	PyErr_Clear();
	Py_RETURN_NONE;
    }
    method = PyObject_GetAttrString(obj, name);
    if (!method)
    {
	/* do nothing if the object doesn't have the method */
	fprintf(stderr, "No Method %s.%s\n", key, name);
	PyErr_Clear();
	Py_RETURN_NONE;
    }

    /* convert the string-marshaled arguments of event-driven methods */
    call_args = NULL;
    if (strcmp(name, "RedrawMethod") == 0 && argc == 3)
    {
	char * ptr = PyString_AsString(PyTuple_GET_ITEM(args, 2));
	if (!ptr)
	{
	    Py_DECREF(method);
	    return NULL;
	}
	call_args = Py_BuildValue(
	    "(N)", PaxRegion_FromRegion((Region) strtoul(ptr, NULL, 10)));
    }
    else if (strcmp(name, "ResizedMethod") == 0 && argc == 4)
	call_args = Py_BuildValue(
	    "(ii)",
	    atoi(PyString_AsString(PyTuple_GET_ITEM(args, 2))),
	    atoi(PyString_AsString(PyTuple_GET_ITEM(args, 3))));
    else if (strcmp(name, "ExtensionEvent") == 0 && argc == 3)
	call_args = Py_BuildValue(
	    "(i)", atoi(PyString_AsString(PyTuple_GET_ITEM(args, 2))));
    else if (argc > 2)
    {
	call_args = PyTuple_New(argc - 2);
	if (call_args)
	    for (i = 2; i < argc; i++)
	    {
		PyObject * string = PyTuple_GET_ITEM(args, i);
		Py_INCREF(string);
		PyTuple_SET_ITEM(call_args, i - 2, string);
	    }
    }
    if (PyErr_Occurred())
    {
	Py_DECREF(method);
	return NULL;
    }

    result = PyObject_CallObject(method, call_args);
    Py_DECREF(method);
    Py_XDECREF(call_args);
    return result;  /* NULL: PythonCmd reports the exception */
}

static PyMethodDef pax_call_py_method_def = {
    "call_py_method",
    (PyCFunction) pax_call_py_method,
    METH_VARARGS,
    "call_py_method(key, methodname, arg...)\n\n"
    "Call the method 'methodname' of the object registered under 'key'."
};

/* Convert a Region pointer marshaled as a decimal string (see
   PaxWidgetDisplay) back into a PaxRegion object. The region ownership
   is transferred to the new object. */
static PyObject *
pax_region_from_ptr(PyObject * self, PyObject * args)
{
    char * ptr;
    if (!PyArg_ParseTuple(args, "s", &ptr))
	return NULL;
    return PaxRegion_FromRegion((Region) strtoul(ptr, NULL, 10));
}


static PyObject *
create_tcl_commands(PyObject * self, PyObject * args)
{
    PyObject * app;
    Tcl_Interp * interp;
    
    if (!PyArg_ParseTuple(args, "O", &app))
	return NULL;

    /* app must be the _tkinter tkapp object (not an interpaddr):
       'call_py_method' is registered via its createcommand method so
       that _tkinter dispatches it with proper GIL and tcl_tstate
       handling (see the comment on pax_call_py_method) */
    if (PyInt_Check(app))
    {
	PyErr_SetString(PyExc_TypeError,
			"create_tcl_commands requires the tkapp object, "
			"not an interpaddr");
	return NULL;
    }

    interp = ((TkappObject*)app)->interp;

    Tcl_CreateCommand(interp, "paxwidget", paxwidget_cmd,
		      (ClientData)Tk_MainWindow(interp), NULL);

    {
	PyObject * func = PyCFunction_New(&pax_call_py_method_def, NULL);
	PyObject * result;
	if (!func)
	    return NULL;
	result = PyObject_CallMethod(app, "createcommand",
				     "sO", "call_py_method", func);
	Py_DECREF(func);
	if (!result)
	    return NULL;
	Py_DECREF(result);
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *
pax_CreateRegion(PyObject * self, PyObject * args)
{
    return PaxRegion_FromRegion(XCreateRegion());
}



static PyMethodDef pax_methods[] = {
    {"IntersectMasks",	PaxClipMask_IntersectMasks,	1},
    {"CreateRegion",	pax_CreateRegion,		1},
    {"register_object",	register_object,		1},
    {"unregister_object",	unregister_object,	1},
    {"name_to_window",	name_to_window,			1},
    {"do_one_event",	do_one_event,			1},
    {"call_py_method",	(PyCFunction) pax_call_py_method, METH_VARARGS},
    {"region_from_ptr",	pax_region_from_ptr,		1},
    {"create_tcl_commands",	create_tcl_commands,	1},
    {NULL, NULL} 
};


static void
add_int(PyObject * dict, int i, char * name)
{
    PyObject *v;
    
    v = Py_BuildValue("i", i);
    if (v)
    {
	PyDict_SetItemString(dict, name, v);
	Py_DECREF(v);
    }
}

static void
add_string(PyObject * dict, char * str, char * name)
{
    PyObject *v;
    
    v = Py_BuildValue("s", str);
    if (v)
    {
	PyDict_SetItemString(dict, name, v);
	Py_DECREF(v);
    }
}

static Pax_Functions pax_functions = {
    PaxPixmap_FromPixmap
};
    


void
initpax(void)
{
    int i;
    PyObject * d, *m, *v;

    m = Py_InitModule("pax", pax_methods);
    d = PyModule_GetDict(m);
    
#define ADD_INT(name) add_int(d, name, #name)
    ADD_INT(TCL_WINDOW_EVENTS);
    ADD_INT(TCL_FILE_EVENTS);
    ADD_INT(TCL_TIMER_EVENTS);
    ADD_INT(TCL_IDLE_EVENTS);
    ADD_INT(TCL_ALL_EVENTS);
    ADD_INT(TCL_DONT_WAIT);
    ADD_INT(TK_RELIEF_RAISED);
    ADD_INT(TK_RELIEF_SUNKEN);
    ADD_INT(TK_RELIEF_GROOVE);
    ADD_INT(TK_RELIEF_RIDGE);
    ADD_INT(TK_RELIEF_FLAT);
    ADD_INT(TK_3D_FLAT_GC);
    ADD_INT(TK_3D_LIGHT_GC);
    ADD_INT(TK_3D_DARK_GC);
    add_string(d, TK_VERSION, "TK_VERSION");
    add_string(d, TCL_VERSION, "TCL_VERSION");
    
    for (i = 0; i < NUM_METHOD_NAMES; i++)
    {
	/* Python 1.5! */
	PyObject * string = PyString_InternFromString(method_names[i]);
	if (!string)
	{
	   Py_FatalError("pax: Cannot create string objects");
	}
	method_names_obj[i] = string;
    }

    object_registry = PyDict_New();
    PyDict_SetItemString(d, "object_registry", object_registry);

    v = PyCObject_FromVoidPtr(&pax_functions, NULL);
    PyDict_SetItemString(d, "Pax_Functions", v);

#define ADD_TYPE(type) PyDict_SetItemString(d, #type, (PyObject*)(&type))

    ADD_TYPE(TkWinType);
    ADD_TYPE(PaxPixmapType);
    ADD_TYPE(PaxImageType);
    ADD_TYPE(PaxRegionType);
    ADD_TYPE(PaxCMapType);
    ADD_TYPE(PaxFontType);
    ADD_TYPE(PaxGCType);
    ADD_TYPE(PaxBorderType);
}
