#!/usr/bin/python

licence={}
licence['en']="""
    file choixEleves.py
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
from Ui_choixEleves import Ui_Dialog
import db
import sys, os.path


class choixElevesDialog(QDialog):
    """
    implémente un dialogue permettant de choisir des élèves
    les propriétés importantes sont self.ok, vrai si on doit prendre en
    compte la liste sélectionnée, et le contenu de la liste des sélectionnés,
    dont on peut récupérer les élèves un par un à l'aide de self.pop()
    """

    def __init__(self, parent=None, gestionnaire=gestClasse.Sconet):
        """
        le constructeur
        récupérer des données SCONET
        @param parent le widget parent
        @param gestionnaire le système censé gérer les données du fichier f
        """
        QDialog.__init__(self, parent=parent)
        self.ok=None
        self.ui=Ui_Dialog()
        self.ui.setupUi(self)
        self.prefs=db.readPrefs()
        self.gestionnaire=gestionnaire
        self.connecteGestionnaire()
        self.ui.listWidget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.ui.listWidget.setSortingEnabled(True)
        self.ui.checkBoxNumero.setChecked(True)
        self.ui.spinBoxNumero.setValue(1)
        self.ui.spinBoxNumero.setEnabled(True)
        self.ui.pushButtonFile.clicked.connect(self.fichierEleves)
        self.ui.pushButton_replierArbre.clicked.connect(self.replie)
        self.ui.pushButton_cocher.clicked.connect(self.coche)
        self.ui.pushButton_decocher.clicked.connect(self.decoche)
        self.ui.pushButton_addToList.clicked.connect(self.addToList)
        self.ui.pushButton_delInList.clicked.connect(self.delInList)
        self.ui.pushButton_OK.clicked.connect(self.valid)
        self.ui.pushButton_Esc.clicked.connect(self.escape)
        self.ui.checkBoxNumero.stateChanged.connect(self.checkNum)

    def fichierEleves(self):
        """
        choisit et ouvre un nouveau fichiers d'élèves
        """
        caption="Choisissez un nouveau fichier de gestion des élèves"
        dirname=os.path.dirname(self.prefs["schoolFile"])
        newFile=QFileDialog.getOpenFileName (self, caption, dirname)
        if os.path.exists(newFile):
            self.prefs["schoolFile"]=newFile
            db.writePrefs(self.prefs)
            self.connecteGestionnaire(renew=True)
        return

    def connecteGestionnaire(self, renew=False):
        """
        met en place l'arbre des noms d'élèves
        @param renew vrai si on veut vider tout l'arbre et recommencer
        """
        try:
            self.ui.lineEditFile.setText(self.prefs["schoolFile"])
            self.ui.treeView.connecteGestionnaire(self.prefs["schoolFile"],
                                                  self.gestionnaire,
                                                  renew=renew)
        except Exception as err:
            QMessageBox.warning(None,
                                QApplication.translate("Dialog","Échec à l'ouverture du fichier élèves",None),
                                QApplication.translate("Dialog","Le fichier {schoolfile} n'a pas pu être traité : {erreur}",None).format(schoolfile=self.prefs["schoolFile"], erreur=err))
    
    def checkNum(self, state):
        """
        fonction de rappel utilisée quand on coche/décoche la case pour
        prendre en compte le numéro
        @param state : l'état coché ou décoché
        """
        if state==Qt.Checked:
            self.ui.spinBoxNumero.setEnabled(True)
        else:
            self.ui.spinBoxNumero.setEnabled(False)
        return
    
    def replie(self):
        """
        replie toutes les classes du dialogue
        """
        self.ui.treeView.collapseAll()
        return

    def coche(self):
        """
        coche toutes les cases d'élèves visibles
        """
        for e in self.ui.treeView.expandedItems():
            e.setCheckState(Qt.Checked)
        return

    def decoche(self):
        """
        décoche toutes les cases d'élèves, visibles ou cachées
        """
        for e in self.ui.treeView.expandedItems():
            e.setCheckState(Qt.Unchecked)
        return

    def updateParentIcon(self):
        """
        Met à jour l'icône du bouton d'activation dans l'application parente
        pour refléter la présence d'éléments dans la liste
        """
        if self.parent():
            self.parent().setAvailableNames(self.ui.listWidget.count() > 0)
        return

    def addToList(self):
        """
        ajoute les élèves cochés dans la liste (s'ils n'y sont pas déjà)
        """
        for n in self.listeUnique_Names():
            if not self.ui.listWidget.findItems(n,Qt.MatchExactly):
                self.ui.listWidget.addItem(n)
        self.updateParentIcon()
        return

    def delInList(self):
        """
        retire les élèves de la liste quand ils y sont sélectionnés
        """
        rows=[]
        for i in self.ui.listWidget.selectedIndexes():
            rows.append(i.row())
        rows.sort(reverse=True)
        for r in rows:
            self.ui.listWidget.takeItem(r)
        self.updateParentIcon()
        return

    def pop(self):
        """
        renvoie et supprime le premier élément de la liste de noms;
        si cette liste est vide, renvoie None
        @return un nom pour un baladeur, sinon None
        """
        if self.ui.listWidget.count() == 0:
            return
        i=self.ui.listWidget.takeItem(0)
        self.updateParentIcon()
        data=i.data(Qt.DisplayRole)
        return data

    def itemStrings(self):
        """
        @return une liste des chaînes contenues dans les items
        """
        itemList=self.ui.listWidget.findItems("*",Qt.MatchWrap | Qt.MatchWildcard)
        l=[i.data(Qt.DisplayRole) for i in itemList]
        l.sort()
        return l

    def takeItem(self, item):
        """
        retire un item de la liste et le renvoie (pourvu qu'il y existe)
        @param une chaîne donnant le texte d'un item à trouver
        @return un nom pour un baladeur, sinon None
        """
        found=self.ui.listWidget.findItems(item,Qt.MatchExactly)
        if len(found) > 0:
            r=self.ui.listWidget.row(found[0])
            i=self.ui.listWidget.takeItem(r)
            self.updateParentIcon()
            data=i.data(Qt.DisplayRole)
            return data
        return ""

    def valid(self):
        """
        Prend acte de la validation
        """
        self.ok=True
        self.close()
        return

    def escape(self):
        """
        Prend acte de l'abandon ; supprime les éléments de la liste et
        ferme le dialogue
        """
        while self.ui.listWidget.count() > 0:
            self.ui.listWidget.takeItem(0)
        self.updateParentIcon()
        self.ok=False
        self.close()
        return

    def listeChoix(self):
        """
        @return la liste de QStandardItems sélectionnés
        """
        return self.ui.treeView.checkedItems()

    def listeUnique_Names(self):
        result=[]
        for e in self.listeChoix():
            prefixe=""
            if self.ui.checkBoxNumero.isChecked():
                n=self.ui.spinBoxNumero.value()
                prefixe="%02d-" %n
                self.ui.spinBoxNumero.setValue(n+1)
            result.append(prefixe+e.unique_name)
        return result

if __name__=="__main__":
    app=QApplication(sys.argv)
    d=choixElevesDialog(gestionnaire=gestClasse.Sconet)
    d.exec_()
    print ("dialogue ok = %s" %d.ok)
    i=d.pop()
    while i:
        print ("on a dépilé %s" %i)
        i=d.pop()

