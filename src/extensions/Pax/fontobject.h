#ifndef FONTOBJECT_h
#define FONTOBJECT_h

typedef struct {
	PyObject_HEAD
	Display *	display;
	XFontStruct *	font_struct;
	int		from_id;
} PaxFontObject;

extern PyTypeObject PaxFontType;
#define PaxFont_Check(xp)	((xp)->ob_type == &PaxFontType)

extern PyObject *PaxFont_FromName (Display *, char *);
extern PyObject *PaxFont_FromFont (Display *, Font);
extern Font PaxFont_AsFont (PyObject *);
extern XFontStruct * PaxFont_AsFontStruct (PyObject *);


#endif /* FONTOBJECT_h */
