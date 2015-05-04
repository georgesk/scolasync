# -*- coding: utf-8 -*-    
# $Id: chooseInSticks.py 47 2011-06-13 10:20:14Z georgesk $	

licenceEn="""
    file chooseInSticks.py
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

python3safe=True

from PyQt4.QtCore import *
from PyQt4.QtGui import *
import os.path

import Ui_chooseInSticks

class chooseDialog(QDialog):
    """
    Un dialogue pour choisir un ensemble de fichiers à copier depuis une clé USB.
    """
    def __init__(self,parent = None, title1="", title2="", okPrompt="OK"):
        """
        Le constructeur
        @param parent un mainWindow, qui est censé contenir des données
        telles que parent.workdir, ...
        @param title1 le titre du dialogue
        @param title2 le titre pour la série de fichiers/modèles
        @param okPrompt le texte du bouton OK
        """
        QDialog.__init__(self,parent)
        self.mainWindow=parent
        self._ui=Ui_chooseInSticks.Ui_Dialog()
        self._ui.setupUi(self)
        ## mise en place des titres personnalisés
        self.setWindowTitle(title1)
        self._ui.groupBox.setTitle(title2)
        ## mise en place du bouton personnalisé
        okButton=self._ui.buttonBox.button(QDialogButtonBox.Ok)
        self._ui.buttonBox.removeButton(okButton)
        self.okButton=QPushButton(okPrompt)
        self._ui.buttonBox.addButton(self.okButton,
                                     QDialogButtonBox.AcceptRole)
        ## création de la structure de liste pour les fichiers
        self._fileListModel=QStandardItemModel()
        self._fileListProxyModel = QSortFilterProxyModel()
        self._fileListProxyModel.setSourceModel(self._fileListModel)
        self._ui.listView.setModel(self._fileListProxyModel)
        self._fileListProxyModel.setDynamicSortFilter(True)
        ## création de la structure de liste pour les noms de baladeurs
        self._storListModel=QStandardItemModel()
        self._storListProxyModel = QSortFilterProxyModel()
        self._storListProxyModel.setSourceModel(self._storListModel)
        self._ui.listChoixCle.setModel(self._storListProxyModel)
        self._storListProxyModel.setDynamicSortFilter(True)
        ## peuplement de la zone des noms de baladeurs
        self.ownedUsbDictionary={}
        self.listStorages()
        ##
        self._ui.minusButton.setEnabled(False)
        self._ui.travailEdit.setText(self.mainWindow.workdir)
        QObject.connect(self._ui.plusButton, SIGNAL("clicked()"), self.plus)
        QObject.connect(self._ui.chooseButton, SIGNAL("clicked()"), self.choose)
        QObject.connect(self._ui.chooseButton_dir, SIGNAL("clicked()"), self.choose_dir)
        QObject.connect(self.okButton, SIGNAL("clicked()"), self.checkValues)
        QObject.connect(self._ui.minusButton, SIGNAL("clicked()"), self.minus)
        QObject.connect(self._ui.listView, SIGNAL("clicked(QModelIndex)"), self.activate)
        QObject.connect(self._ui.travailEdit, SIGNAL("editingFinished()"), self.changeWd)
        self.ok=False

    def checkValues(self):
        """
        fonction de rappel liée au bouton de validation, vérifie s'il y a bien
        au moins un fichier ou un répertoire sélectionné
        """
        self.ok=self._ui.listView.model().rowCount()>0
        
    def listStorages(self):
        """
        Met en place la liste des noms de baladeurs connectés en tenant compte
        du nom de répertoire de travail et d'un baladeur éventuellement
        sélectionné dans la fenêtre principale
        """
        sel=self.mainWindow.ui.tableView.selectedIndexes()
        print("GRRR in listStorages qApp.available=", qApp.available)
        for d in qApp.available:
            o=qApp.available.targets[d].ownerByDb()
            mountPath=d.ensureMounted()
            item=QStandardItem(o)
            # on cherche à voir si la clé est déjà sélectionnée
            for modelIndex in sel:
                if o == "%s" %modelIndex.data(Qt.DisplayRole).toString():
                    break
            self._storListModel.appendRow(item)
            self.ownedUsbDictionary[o]=mountPath
        self._storListProxyModel.sort(0)
        self.checkWorkDirs()

    def checkWorkDirs(self):
        """
        met à jour la possibilité de sélectionner les baladeurs dans la liste
        selon qu'ils ont ou pas un répertoire de travail, puis sélectionne
        si possible un baladeur, si aucun ne l'était avant.
        """
        firstSelectable=None
        okSelected=None
        # on récupère la sélection courante à travers le proxy
        selection=self._ui.listChoixCle.selectionModel().selection()
        selection = self._storListProxyModel.mapSelectionToSource(selection)
        selectedRows=map(lambda x: x.row(), self._ui.listChoixCle.selectedIndexes())
        itemList=self._storListModel.findItems ("*",Qt.MatchWildcard)
        itemList.sort(key=lambda i: i.data(Qt.DisplayRole).toString())
        # parcours des items de la liste par ordre alphabétique
        # pour élire celui qui sera sélectionné initialement
        for item in itemList:
            index=self._storListModel.indexFromItem(item)
            o="%s" %item.data(Qt.DisplayRole).toString()
            testDir=os.path.join(self.ownedUsbDictionary[o],self.mainWindow.workdir)
            if os.path.isdir(testDir):
                # si l'item concerne un disque qui contient le répertoire de
                # travail, on le rend sélectionnable
                item.setSelectable(True)
                item.setEnabled(True)
                # et si c'est le tout premier, on s'en souvient.
                if firstSelectable == None:
                    firstSelectable=index
                # on vérifie s'il était déjà dans la sélection
                if index.row() in selectedRows:
                    okSelected=index
            else:
                item.setSelectable(False)
                item.setEnabled(False)
        if okSelected == None and firstSelectable != None:
            selection=QItemSelection(firstSelectable,firstSelectable)
            selection=self._storListProxyModel.mapSelectionFromSource(selection)
            self._ui.listChoixCle.selectionModel().select(selection, QItemSelectionModel.Select);

    def baseDir(self):
        """
        @return le répertoire à partir duquel on peut commencer à faire
        un choix de fichier ou de sous-répertoire. Il dépend du baladeur
        sélectionné s'il y en a un et du nom du répertoire de travail.
        Si on n'arrive pas à déterminer ce répertoire, renvoie None
        """
        mp=self.selectedDiskMountPoint()
        if mp:
            return os.path.join(mp,self.mainWindow.workdir)
        else:
            return None

    def selectedDiskMountPoint(self):
        """
        @return le point de montage du support sélectionné s'il y en a un
        """
        o=self.selectedDiskOwner()
        if o==None:
            return None
        else:
            return self.ownedUsbDictionary[o]

    def selectedDiskOwner(self):
        """
        @return le nom du propriétaire du disque sélectionné s'il y en a un,
        sinon None.
        """
        selection=self._ui.listChoixCle.selectionModel().selection()
        if len(selection)==0:
            return None
        selection = self._storListProxyModel.mapSelectionToSource(selection)
        return "%s" %selection.indexes()[0].data(Qt.DisplayRole).toString()
                
    def changeWd(self):
        """
        changement du répertoire de travail
        """
        newDir=self._ui.travailEdit.text()
        self.mainWindow.changeWd(newDir)
        self.checkWorkDirs()

    def choose(self, kind="file"):
        """
        Facilite le choix de motifs de fichiers en recherchant dans
        les clés USB, modifie l'éditeur de ligne de texte et place le
        fichier choisi dans la liste
        @param kind type d'élément à choisir : "file" pour un fichier,
        "dir" pour un répertoire
        """
        if kind == "file":
            func=QFileDialog.getOpenFileNames
            msg=QApplication.translate("Dialog",
                                       "Choissez un fichier (ou plus)",
                                       encoding=QApplication.UnicodeUTF8)
        else:
            func=QFileDialog.getExistingDirectory
            msg=QApplication.translate("Dialog",
                                       "Choissez un répertoire",
                                       encoding=QApplication.UnicodeUTF8)
        cd=self.baseDir()
        if cd!=None:
            f = func (None, msg, cd)
            if f and len(f)>0:
                if isinstance(f, str):
                    theList=[f]
                else:
                    theList=f
                for f in theList:
                    path=f.replace(self.selectedDiskMountPoint()+"/", "")
                    self._ui.lineEdit.setText(path)
                    self.plus()
        else:
            titre=QApplication.translate("Dialog",
                                         "Aucune clé modèle sélectionnée",
                                         encoding=QApplication.UnicodeUTF8)
            msg=QApplication.translate("Dialog",
                                       "Veuillez choisir une clé modèle<br>parmi les clés connectées en cliquant<br>sur une ligne du tableau, pour<br>bénéficier de l'aide au choix de fichiers.<br><br>Cette clé doit contenir au moins<br>un répertoire « {workdir} ».".format(workdir=self.mainWindow.workdir),
                                       encoding=QApplication.UnicodeUTF8)
            msgBox=QMessageBox.warning(None, titre, msg)
        
    def choose_dir(self):
        """
        Facilite le choix de motifs de répertoires en recherchant dans
        les clés USB, modifie l'éditeur de ligne de texte et place le
        répertoire choisi dans la liste
        """
        self.choose(kind="dir")
        
    def activate(self, item):
        """
        Fonction de rappel quand un item de la liste est activé
        @param item désignation de l'item activé
        """
        self._ui.minusButton.setEnabled(True)
        
    def plus(self):
        """
        Permet de choisir et d'ajouter un nouveau fichier ou répertoire à
        supprimer
        """
        text=self._ui.lineEdit.text()
        if len(text)>0 :
            self.append(text)
        
    def minus(self):
        """
        Permet de retirer de la liste des fichiers à supprimer ceux qu'on
        a sélectionnés
        """
        sel=self._ui.listView.selectedIndexes()
        sel1=map(self._fileListProxyModel.mapToSource,sel)
        rows=map(lambda x: x.row(), sel1)
        rows.sort("descending")
        for r in rows:
            self._fileListModel.removeRow(r)
        sel=self._ui.listView.selectedIndexes()
        if len(sel)==0:
            self._ui.minusButton.setEnabled(False)
        
    def append(self, path):
        """
        Ajoute un chemin avec ou sans jokers à la liste des chemins à supprimer
        @param path le chemin
        """
        f=self._fileListModel.findItems(path)
        if len(f)==0:
            item=QStandardItem(path)
            self._fileListModel.appendRow(item)
            self._fileListProxyModel.sort(0)
        else:
            print ("%s est déjà sélectionné" %path)

    def pathList(self):
        """
        renvoie la liste des chemins sélectionnés; dans le cas de chemins
        sans jokers (caractères * ou ?), les chemins sont protégés par des
        guillemets, afin qu'ils soient adaptés à un shell POSIX.
        @return une liste de chemins, sous forme de QStrings
        """
        itemList=self._fileListModel.findItems("*",Qt.MatchWildcard)
        result=[x.text() for x in itemList]
        otherText=self._ui.lineEdit.text()
        if len(otherText) > 0 and otherText not in result :
            result.append(otherText)
        return result

        
        
