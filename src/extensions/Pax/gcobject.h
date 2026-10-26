#ifndef GCOBJECT_H
#define GCOBJECT_H

typedef struct PaxGCObject_
{
    PyObject_HEAD
    Display *	display;
    Drawable	drawable;
    GC		gc;
    int		shared;
    PyObject *	drawable_object;
} PaxGCObject;

#define PAXGC_OWNED 0
#define PAXGC_SHARED 1
#define PAXGC_BORROWED 2

extern PyTypeObject PaxGCType;
#define PaxGC_Check(x)	((x)->ob_type == &PaxGCType)

int PaxGC_MakeValues (PyObject *, unsigned long *, XGCValues *);
PyObject *PaxGC_FromGC (Display *, Drawable, GC, int, PyObject*);
GC PaxGC_AsGC (PyObject *);

int paxtk_checkshortlist(int width, PyObject *list,
			 short **parray, int *pnitems);


#endif /* GCOBJECT_H */
