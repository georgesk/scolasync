licenceEn="""
    file checkBoxDialog.py
    this file is part of the project scolasync
    
    Copyright (C) 2010 Georges Khaznadar <georgesk@ofset.org>

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

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import Ui_checkBoxDialog

class CheckBoxDialog(QDialog):
    """
    Un dialogue pour gérer les cases à cocher de l'application
    """
    def __init__(self,parent = None):
        """
        Le constructeur
        @param parent un mainWindow, qui est censé contenir des données
        """
        QDialog.__init__(self,parent)
        self.mainWindow=parent
        self.ui=Ui_checkBoxDialog.Ui_checkBoxDialog()
        self.ui.setupUi(self)
        self.ui.allButton.clicked.connect(self.all)
        self.ui.ToggleButton.clicked.connect(self.toggle)
        self.ui.NoneButton.clicked.connect(self.none)
        self.ui.escButton.clicked.connect(self.esc)

    def all(self):
        """
        Fait cocher tous les baladeurs
        """
        self.mainWindow.checkAllSignal.emit()
        self.close()

    def toggle(self):
        """
        Fait inverser tous les boutons
        """
        self.mainWindow.checkToggleSignal.emit()
        self.close()

    def none(self):
        """
        Fait décocher tous les boutons
        """
        self.mainWindow.checkNoneSignal.emit()
        self.close()

    def esc(self):
        """
        termine le dialogue sans rien faire
        """
        self.close()
    
