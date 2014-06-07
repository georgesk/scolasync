#!/usr/bin/python
# -*- coding: utf-8 -*-
# 	$Id: preferences.py 42 2011-01-15 22:38:04Z georgesk $	

licence={}
licence['en']="""
    file preferences.py
    this file is part of the project scolasync
    
    Copyright (C) 2010-2012 Georges Khaznadar <georgesk@ofset.org>

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

python3safe=True

from PyQt4.QtCore import *
from PyQt4.QtGui import *

class preferenceWindow(QDialog):
    def __init__(self, parent=None):
        """
        Le constructeur
        """
        QDialog.__init__(self, parent)
        from Ui_preferences import Ui_Dialog
        self.ui=Ui_Dialog()
        self.ui.setupUi(self)
        self.connect(self.ui.refreshEnabledBox, SIGNAL("stateChanged(int)"), self.enableDelay)
        self.connect(self.ui.refreshDelaySlider, SIGNAL("valueChanged(int)"), self.updateRefreshLabel)

    def enableDelay(self, state):
        """
        active ou désactive le glisseur pour modifier le délai de rafraichissement
        @param state l'état coché ou décoché de la boîte qui contrôle le rafraichissement
        """
        self.ui.refreshDelaySlider.setEnabled(bool(state))

    def updateRefreshLabel(self, val):
        """
        Met à jour l'affichage de la valeur du délai de rafraichissement
        @param val un nombre entier qui exprime le délai en secondes
        """
        labelTxt=QApplication.translate("Dialog", "{t} secondes", None, QApplication.UnicodeUTF8)
        val="%2d" %val
        labelTxt=labelTxt.format(t=val)
        self.ui.refreshDelayLabel.setText(labelTxt)

    def values(self):
        """
        @return un dictionnaire de préférences
        """
        prefs={}
        prefs["checkable"]      = True
        prefs["mv"]             = bool(self.ui.mvCheck.isChecked())
        prefs["schoolFile"]     = self.ui.lineEditSchoolFile.text()
        prefs["workdir"]        = self.ui.dirEdit.text()
        prefs["manfile"]        = self.ui.manFileEdit.text()
        prefs["refreshEnabled"] = bool(self.ui.refreshEnabledBox.isChecked())
        prefs["refreshDelay"]   = self.ui.refreshDelaySlider.value()
        return prefs

    def setValues(self, prefs):
        """
        Met en place les préférences dans le dialogue
        @param prefs un dictionnaire de préférences
        """
        if prefs["mv"]:
            state=Qt.Checked
        else:
            state=Qt.Unchecked
        self.ui.mvCheck.setCheckState(state)
        if prefs["refreshEnabled"]:
            state=Qt.Checked
        else:
            state=Qt.Unchecked
        self.ui.refreshEnabledBox.setCheckState(state)
        self.ui.refreshDelaySlider.setEnabled(prefs["refreshEnabled"])
        self.ui.lineEditSchoolFile.setText(prefs["schoolFile"])
        self.ui.dirEdit.setText(prefs["workdir"])
        self.ui.manFileEdit.setText(prefs["manfile"])
        self.ui.refreshDelaySlider.setValue(prefs["refreshDelay"])
