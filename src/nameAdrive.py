#!/usr/bin/python

licence={}
licence['en']="""
    file nameAdrive.py
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

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import Ui_nameAdrive
import re
import db

class nameAdriveDialog(QDialog):
    """
    un dialogue pour renommer un baladeur, compte tenu d'une liste
    de noms disponibles
    """

    def __init__(self, parent=None, oldName="", nameList=[], driveIdent=None):
        """
        Le constructeur.
        @param parent le widget parent
        @param oldName le nom précédent du baladeur
        @param nameList une liste de noms disponibles
        @param driveIdent identité d'un baladeur sous forme d'un triplet (stickId, Uuid, Tattoo)
        """
        QDialog.__init__(self, parent)
        self.oldName=oldName
        self.nameList=nameList
        assert driveIdent != None
        self.stickId, self.uuid, self.tattoo = driveIdent
        self.ui=Ui_nameAdrive.Ui_Dialog()
        self.ui.setupUi(self)
        for n in self.nameList:
            self.ui.listWidget.addItem(n)
        self.ui.lineEditOld.setText(self.oldName)
        self.numPattern=re.compile("^([0-9][0-9][0-9]?)-.*")
        self.ui.listWidget.itemSelectionChanged.connect(self.selectionChanged)
        self.ui.pushButtonOK.clicked.connect(self.ok)
        self.ui.pushButtonEsc.clicked.connect(self.esc)
        self.makeSelection()

    def makeSelection(self):
        """
        Si l'ancien nom commence par un numéro, sélectionne le premier élément
        de la liste commençant par le même, sinon sélectionne le tout premier
        élément de la liste.
        """
        m=self.numPattern.match("%s" %self.oldName)
        lw=self.ui.listWidget
        if m:
            num=m.group(1)
            regexp="^%s-.*" %num
            possible=lw.findItems(regexp,Qt.MatchRegExp)
            if len(possible) > 0:
                lw.setCurrentItem(possible[0])
            else:
                lw.setCurrentItem(lw.item(0))
        else:
            lw.setCurrentItem(lw.item(0))
        return

    def selectionChanged(self):
        """
        fonction de rappel quand la sélection change dans la liste;
        recopie l'élément sélectionné comme nouveau nom de baladeur
        """
        l=self.ui.listWidget.selectedItems()
        i=l[0]
        t=i.data(Qt.DisplayRole)
        self.ui.lineEditNew.setText(t)
        return

    def ok(self):
        """
        fonction de rappel quand l'utilisateur valide le choix
        """
        newName="%s" %self.ui.lineEditNew.text()
        newName.encode("utf-8")
        db.writeStudent(self.stickId, self.uuid, self.tattoo, newName)
        self.parent().namesDialog.takeItem(newName)
        self.parent().checkDisks(noLoop=True)
        self.done(QDialog.Accepted)
        return

    def esc(self):
        """
        fonction de rappel quand l'utilisateur cherche à échapper au choix
        """
        self.done(QDialog.Rejected)
        return
    
