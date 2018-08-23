# skencil-tk
Skencil drawing application

Continuation of the Skencil project: http://www.skencil.org

To compile, run `python setup.py build` and then start directly
from the `build/` directory.

This work is heavily based on skencil-1.0alpha by Igor E. Novikov.

### New features:

- Arrows which don't extend beyond path ends
- Saving inlined images in PNG format (much smaller file size)
- Option to scale line width when transforming the object
- Automatic reloading of linked images
- Move selection with keyboard keys, like in many other drawing programs
- PDF export which works
- Buttons for 90 degree rotation of the selection
- Draw text as curves if X11 font is not found
- Scroll canvas by dragging the middle mouse button and zoom in/out with the wheel
- Feedback for saving and exporting
- New types of plugin parameters

And many bug fixes.
