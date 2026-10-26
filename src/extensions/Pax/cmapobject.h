#ifndef CMAPOBJECT_H
#define CMAPOBJECT_H

extern PyTypeObject PaxCMapType;
#define PaxCMap_Check(obj)	((obj)->ob_type == &PaxCMapType)

extern PyObject * PaxCMap_FromColormap (Colormap, Display *, int);

Colormap PaxCMap_AsColormap(PyObject*);

#endif /* CMAPOBJECT_H */
