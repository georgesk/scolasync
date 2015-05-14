# $Id: copyToDialog1.py 47 2011-06-13 10:20:14Z georgesk $	

licenceEn="""
    file copyToDialog1.py
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
from PyQt5.QtGui import *
import os.path, subprocess

import Ui_copyToDialog1

class copyToDialog1(QDialog):
    """
    Un dialogue pour choisir un ensemble de fichiers à transférer vers
    une collection de clés USB.
    @param parent un widget
    @param workdir un répertoire cible sur les baladeurs
    """
    def __init__(self,parent = None, workdir=""):
        """
        Le constructeur
        @param parent un QWidget
        """
        QDialog.__init__(self,parent)
        self.mainWindow=parent
        self._ui=Ui_copyToDialog1.Ui_Dialog()
        self._ui.setupUi(self)
        self._ui.travailEdit.setText(workdir)
        self.setupFromListe()
        self._fromDir=QDir.home()
        self.setFromListeDir(self._fromDir)
        self.setupToListe()
        ##
        # \var ok vrai si on a cliqué sur Continuer ...
        self.ok="False"
        self._ui.selectButton.clicked.connect(self.select)
        self._ui.removeButton.clicked.connect(self.remove)
        self._ui.cancelButton.clicked.connect(self.cancel)
        self._ui.continueButton.clicked.connect(self.cont)
        self._ui.travailEdit.editingFinished.connect(self.changeWd)

    def changeWd(self):
        """
        changement du répertoire de travail
        """
        newDir=self._ui.travailEdit.text()
        self.mainWindow.changeWd(newDir)

    def cancel(self):
        """
        L'action provoquée par le bouton d'échappement : fermeture du dialogue
        """
        self.close()

    def cont(self):
        """
        L'action provoquée par le bouton de continuation : fermeture du dialogue
        et self.ok devient vrai.
        """
        self.ok=True
        self.close()
        
    def setupFromListe(self):
        """
        Met en place un visionneur de fichiers dans la liste source
        """
        self._model1 = QDirModel()
        self._model1.setFilter(QDir.AllEntries)
        self._ui.listViewFrom.setModel(self._model1)
        self._ui.listViewFrom.doubleClicked.connect(self.cd)
        
    def setFromListeDir(self,directory):
        """
        Choisit un répertoire pour la liste source
        @param directory une instance de QDir
        """
        path=directory.path()
        cwdIndex = self._model1.index(path)
        self._ui.listViewFrom.setRootIndex(cwdIndex)
        self._ui.lineEdit.setText(path)

    def cd(self,index):
        """
        Change le répertoire courant si possible
        @param ev un évènement
        """
        d= "%s" %index.data()
        p= "%s" %self._fromDir.path()
        j=os.path.abspath(os.path.join(p,d))
        if os.path.isdir(j):
            self._fromDir=QDir(j)
            self.setFromListeDir(self._fromDir)
        
    def setupToListe(self):
        """
        Met en place un visionneur de fichierspour les fichiers reçus
        """
        self._model2 = QStandardItemModel()
        ### on connecte la liste d'items standard via un
        ### proxy qui autorise le tri alphabétique
        self._proxyModel = QSortFilterProxyModel()
        self._proxyModel.setSourceModel(self._model2)
        self._ui.listViewTo.setModel(self._proxyModel)
        self._proxyModel.setDynamicSortFilter(True)
        ###### apparemment les drops venus de la liste voisine
        ###### ne fonctionnent pas et c'est bien dommage !!!
        ## self._ui.listViewTo.setDragEnabled(True)
        ## self._ui.listViewTo.setAcceptDrops(True)
        ## self._ui.listViewTo.setDropIndicatorShown(True);

    def select(self):
        """
        Ajoute le répertoire ou le fichier sélectionné dans le
        navigateur de fichiers à la liste de sélections.
        """
        sel=self._ui.listViewFrom.selectedIndexes()
        if len(sel)>0:
            index=sel[0]
            d= "%s" %index.data()
            p= "%s" %self._fromDir.path()
            j=os.path.abspath(os.path.join(p,d))
            f=self._model2.findItems(j)
            if len(f)==0:
                self._model2.appendRow(QStandardItem(j))
                self._proxyModel.sort(0)
                # on lance un calcul à nouveau pour la taille totale occupée
                self.displaySize()
            else:
                print ("%s est déjà sélectionné" %j)

    def displaySize(self):
        """
        Affiche la taille de la sélection courante
        """
        total=0
        for path in self.selectedList():
            p=subprocess.Popen("du -s '%s' | awk '{print $1}'" %path,
                               shell=True, stdout=subprocess.PIPE)
            size=p.communicate()[0]
            try:
                total+= int(size)
            except:
                pass
        unit="%s" %QApplication.translate("Dialog","%s kilo-octets",None)
        if total>1024:
            total= 0.1*int(10*total/1024)
            unit="%s" %QApplication.translate("Dialog","%s méga-octets",None)
        if total>1024:
            total= 0.1*int(10*total/1024)
            unit="%s" %QApplication.translate("Dialog","%s giga-octets",None)
        self._ui.lineEdit_size.setText(unit %total)

    def remove(self):
        """
        Supprime le répertoire ou le fichier sélectionné dans la
        liste de sélections.
        """
        sel=self._ui.listViewTo.selectedIndexes()
        if len(sel)>0:
            index=sel[0]
            sourceIndex=self._proxyModel.mapToSource(index)
            self._model2.removeRow(sourceIndex.row())
            self._proxyModel.sort(0)
            # on lance un calcul à nouveau pour la taille totale occupée
            self.displaySize()

    def selectedList(self):
        """
        Renvoie une liste de répertoires et de fichiers qui ont été
        sélectionnés pour la copie sur clé USB.
        @return une liste de QStrings
        """
        sl=self._model2.findItems("*",Qt.MatchWildcard)
        return map(lambda x: ("%s" %x.text()), sl)
        
if __name__=="__main__":
    import sys
    app = QApplication(sys.argv)
    windows = copyToDialog1()
    windows.show()
    sys.exit(app.exec_())
