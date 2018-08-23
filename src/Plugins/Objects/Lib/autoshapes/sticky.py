from Sketch import const

class Sticky:
    
    bond_list = ()

    def sticky_activate(self):
        self.document.Subscribe(const.SELECTION, self.selection_changed)

    def sticky_passivate(self):
        self.bond_list = ()
        self.document.Unsubscribe(const.SELECTION, self.selection_changed)

    def selection_changed(self, *args):
        self.rebuild_bond_list() # XXX reduce this to the investigation of
                                 #     the objects in selection
        
    def doc_modified(self, *args):
        self.rebuild_bond_list()
        
    def rebuild_bond_list(self, verbose=1):
        print "rebuilding bond list"
        doc = self.document
        if doc is None:
            return
        
        old = self.bond_list
        new = self.bond_list = []
        exclude = [self]
        points = self.GetStickyPoints()
        doc.WalkHierarchy(lambda obj, s=self, p=points, n=new, v=verbose: \
                          s.get_bonds_from_obj(obj, p, n, v))

        for item in old:
            if item not in new:
                obj, i, j = item
                print "unsubscribing ", obj
                obj.Unsubscribe(const.CHANGED, self.client_changed, i, j)

        for item in new:
            if item not in old:
                obj, i, j = item
                obj.Subscribe(const.CHANGED, self.client_changed, i, j)
                print "subscribing to ", obj, i, j

    def client_changed(self, obj, i, j):
        print "client changed: ", obj
        p = obj.GetSnapPoints()[i]
        self.bond_changed(j, p)
                                
    def get_bonds_from_obj(self, obj, sticky_points, bonds, verbose=0):
        # Examine all snap points of object whether it is at the same position
        # as one of self's sticky points. Matches are appended to bonds.

        if verbose:
            print "investigating ", obj
            
        if isinstance(obj, StickyObject):
            return

        epsilon = 1e-7
        
        i = 0 # numbers snap points
        for snap in obj.GetSnapPoints():
            j = 0 # numbers sticky_points
            for p in sticky_points:
                if (p-snap).polar()[0] < epsilon:
                    bonds.append((obj, i, j))
                j = j+1
            i = i+1

    ### this has to be implemented by derived classes:
    def bond_changed(self, i, p):
        pass
