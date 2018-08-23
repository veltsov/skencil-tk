
import Sketch
from Sketch import _, Point, Scale, SingularMatrix, NullUndo
from Sketch.Graphics import handle

from  autoshapelib import AutoshapeBase

class Raster(AutoshapeBase):
    
    rows = ()
    lines = ()

    help_text = _("""
Raster
~~~~~~
Keys:
    right   append column
    left    remove column 
    up      append row
    down    remove row

Modifier:
    none
    """)
    
    def __init__(self, *args, **kw):
        self.rows = []
        self.cols = []
        f = 60
        n = 4
        for i in range(n):
            self.rows.append(f*i/float(n))
        for i in range(n):
            self.cols.append(f*i/float(n))
        apply(AutoshapeBase.__init__, (self,)+args, kw)

    def Info(self):
        return "Raster (%s x %s)" % (len(self.cols)-1, len(self.rows)-1)
           
    def GetSnapPoints(self):       
        points = []
        for x in self.cols:
            for y in self.rows:
                points.append(Point(x,y))
        return map(self.trafo, points)

    def LayoutPoint(self):
        return Point(self.cols[0], self.rows[0])

    def Snap(self, point):
        # Determine the point Q on self's outline closest to P and
        # return a tuple (abs(Q - P), Q)
        try:
            p = self.trafo.inverse()(point)
        except SingularMatrix:
            return (1e100, point)
                    
        best_d = 1e100
        best_p = None
        
        y = p[1]
        for x in self.cols:
            t = Point(x, y)
            dist = (t-p).polar()[0]
            if dist < best_d:
                best_d = dist
                best_p = t

        x = p[0]
        for y in self.rows:
            t = Point(x, y)
            dist = (t-p).polar()[0]
            if dist < best_d:
                best_d = dist
                best_p = t

        return (best_d, self.trafo(best_p))
    
    def GetHandles(self):
        handles = []
        for x in self.cols:
            for y in self.rows:
                p = Point(x,y)
                handles.append(handle.MakeNodeHandle(self.trafo(p)))
        return handles
                
    def recompute(self):
        paths = []

        self.rows.sort()
        self.cols.sort()
        
        y0 = self.rows[0]
        y1 = self.rows[-1]
        x0 = self.cols[0]
        x1 = self.cols[-1]

        # make an outer rectangle which can be filled
        path = Sketch.CreatePath()
        paths.append(path)
        path.AppendLine((x0, y0))
        path.AppendLine((x1, y0))
        path.AppendLine((x1, y1))
        path.AppendLine((x0, y1))
        path.AppendLine((x0, y0))

        # the columns ...
        for x in self.cols[1:-1]:
            path = Sketch.CreatePath()
            paths.append(path)
            path.AppendLine((x, y0))
            path.AppendLine((x, y1))

        # the rows ...
        for y in self.rows[1:-1]:
            path = Sketch.CreatePath()
            paths.append(path)
            path.AppendLine((x0, y))
            path.AppendLine((x1, y))

        
        for path in paths:
            path.Transform(self.trafo)
        if self.objects:
            self.objects[0].SetPaths(paths)
        else:
            obj = Sketch.PolyBezier(tuple(paths))
            obj.SetProperties(line_cap=Sketch.const.CapButt)
            self.set_objects([obj])
            
    def DragHandle(self, pa, pb, selection):
        try:
            inverse = self.trafo.inverse()
        except:
            return
        
        pa, pb = map(inverse, (pa, pb))
        dw, dh = pb-pa

        i_row = (selection-1) % len(self.rows)
        i_col = (selection-1) / len(self.rows)

        self.rows[i_row] = self.rows[i_row] + dh
        self.cols[i_col] = self.cols[i_col] + dw
        self.recompute()
        
    def SetData(self, data, version=None):
        rows, cols = data
        self.rows = rows[:]
        self.cols = cols[:]

    def GetData(self):
        return self.rows[:], self.cols[:]

    def InsertCells(self, col=None,row=None):
        cols =self.cols
        rows = self.rows
        
        n_cols = len(cols)
        n_rows = len(rows)
        
        y0 = rows[0]
        y1 = rows[-1]
        x0 = cols[0]
        x1 = cols[-1]

        if col is not None:
            cols.append(col)
        else:
            cols.append(x0+(x1-x0)*float(n_cols)/(n_cols-1))
        if row is not None:
            rows.append(row)
        else:
            rows.append(y0+(y1-y0)*float(n_cols)/(n_cols-1))
        self.recompute()
        return self.RemoveCells,

    def RemoveCells(self):
        cols =self.cols
        rows = self.rows
        
        n_cols = len(cols)
        n_rows = len(rows)

        if n_cols <= 2 or n_rows <= 2:
            return NullUndo
    
        col =  cols.pop()            
        row = rows.pop()
        self.recompute()
        return self.InsertCells, col, row

    def InsertRow(self, col=None,row=None):
        rows = self.rows
        n_rows = len(rows)        
        y0 = min(rows)
        y1 = max(rows)        
        if row is not None:
            rows.append(row)
        else:
            rows.append(y0+(y1-y0)*float(n_rows)/(n_rows-1))
        self.recompute()
        return self.RemoveRow,
    
    def RemoveRow(self):
        rows = self.rows        
        n_rows = len(rows)
        if n_rows <= 2:
            return NullUndo
        row = rows.pop()
        self.recompute()
        return self.InsertRow, row

    def InsertCol(self, col=None):
        cols = self.cols
        n_cols = len(cols)        
        x0 = min(cols)
        x1 = max(cols)        
        if col is not None:
            cols.append(col)
        else:
            cols.append(x0+(x1-x0)*float(n_cols)/(n_cols-1))
        self.recompute()
        return self.RemoveCol,
    
    def RemoveCol(self):
        cols = self.cols
        n_cols = len(cols)
        if n_cols <= 2:
            return NullUndo
        col = cols.pop()
        self.recompute()
        return self.InsertCol, col
    
    def KeyHandler(self, key):
        if key == '+':
            return self.InsertCells()
        elif key == '-':
            return self.RemoveCells()
        elif key == 'Right':
            return self.InsertCol()
        elif key == 'Left':
            return self.RemoveCol()
        elif key == 'Up':
            return self.InsertRow()
        elif key == 'Down':
            return self.RemoveRow()


def register():
    return Raster
