#!/usr/bin/python

licence={}
licence['en']="""
    file gestclassetreeview.py
    this file is part of the project scolasync
    
    Copyright (C) 2012 Georges Khaznadar <georgesk@ofset.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import gestClasse
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

class gestClasseTreeView(QTreeView):
    def __init__(self, parent=None):
        """
        Le constructeur
        @param parent un parent pour le widget
        """
        QTreeView.__init__(self, parent)
        self.gest=None
        model=QStandardItemModel()
        self.setModel(model)
        self.root = self.model().invisibleRootItem()
        return

    def connecteGestionnaire(self, fichier, gestionnaire=gestClasse.Sconet, renew=False):
        """
        @param fichier le nom d'un fichier, ou un fichier ouvert en lecture, pour
        récupérer des données SCONET
        @param gestionnaire un gestionnaire pour exploiter les données du fichier
        @param renew vrai si on doit tout effacer avant de recommencer
        """
        if renew:
            m=self.model()
            m.removeRows(0, m.rowCount())
            self.root = self.model().invisibleRootItem()
        self.gest=gestionnaire(fichier)
        for c in self.gest.collectClasses():
            rowClasse=[QStandardItem(c)]
            self.root.appendRow(rowClasse)
            for e in self.gest.elevesDeClasse(c):
                name=self.gest.showable_name(e)
                eleveItem=QStandardItem(name)
                eleveItem.setCheckable(True)
                eleveItem.unique_name=self.gest.unique_name(e)
                rowEleve=[eleveItem]
                rowClasse[0].appendRow(rowEleve)
        self.setExpanded(self.model().index(0,0),True)
        return

    def expandedItems(self):
        """
        @return la liste des items non repliés (donc visibles)
        """
        result=[]
        m=self.model()
        for r in range(m.rowCount()):
            cl=m.item(r)
            if self.isExpanded(cl.index()):
                for r1 in range(cl.rowCount()):
                    e=cl.child(r1)
                    result.append(e)
        return result

    def allItems(self):
        """
        @return la liste de tous les élèves
        """
        result=[]
        m=self.model()
        for r in range(m.rowCount()):
            cl=m.item(r)
            for r1 in range(cl.rowCount()):
                e=cl.child(r1)
                result.append(e)
        return result

    def checkedItems(self):
        """
        @return la liste de tous les élèves sélectionnés
        """
        result=[]
        m=self.model()
        for r in range(m.rowCount()):
            cl=m.item(r)
            for r1 in range(cl.rowCount()):
                e=cl.child(r1)
                if e.checkState():
                    result.append(e)
        return result

