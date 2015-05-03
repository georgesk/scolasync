#!/usr/bin/python
# -*- coding: utf-8 -*-
# 	$Id: mainWindow.py 47 2011-06-13 10:20:14Z georgesk $	

licence={}
licence['en']="""
    file mainWindow.py
    this file is part of the project scolasync
    
    Copyright (C) 2010-2014 Georges Khaznadar <georgesk@ofset.org>

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


from PyQt4.QtCore import *
from PyQt4.QtGui import *
import ownedUsbDisk, help, copyToDialog1, chooseInSticks, usbThread
import diskFull, preferences, checkBoxDialog
import os.path, operator, subprocess, dbus, re, time, copy
from notification import Notification
from usbDisk2 import safePath
import db
import choixEleves
import nameAdrive
from globaldef import logFileName, _dir

# cette donnée est globale, pour être utilisé depuis n'importe quel objet
qApp.available=ownedUsbDisk.Available(access="firstFat")

activeThreads={} # donnée globale : les threads actifs
# cette donnée est mise à jour par des signaux émis au niveau des threads
# et elle est utilisée par la routine de traçage des cases du tableau
pastCommands={}  # donnée globale : les commandes réalisées dans le passé
lastCommand=None # donnée globale : la toute dernière commande

def registerCmd(cmd,partition):
    """
    enregistre la commande cmd pour la partition donnée
    @param cmd une commande pour créer un thread t
    @param partition une partition
    """
    global pastCommands, lastCommand
    if cmd in pastCommands:
        pastCommands[cmd].append(partition.owner)
    else:
        pastCommands[cmd]=[partition.owner]
    lastCommand=cmd

class mainWindow(QMainWindow):
    def __init__(self, parent, locale="fr_FR"):
        """
        Le constructeur
        @param parent un QWidget
        @param locale la langue de l'application
        """
        QMainWindow.__init__(self)
        QWidget.__init__(self, parent)
        self.locale=locale
        from Ui_mainWindow  import Ui_MainWindow
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.copyfromIcon=QIcon("/usr/share/icons/Tango/scalable/actions/back.svg")
        self.movefromIcon=QIcon("/usr/share/scolasync/images/movefrom.svg")
        # crée le dialogue des nouveaux noms
        self.namesFullIcon=QIcon("/usr/share/icons/Tango/scalable/actions/gtk-find-and-replace.svg")
        self.namesEmptyIcon=QIcon("/usr/share/icons/Tango/scalable/actions/gtk-find.svg")
        self.namesFullTip=QApplication.translate("MainWindow", "<br />Des noms sont disponibles pour renommer les prochains baladeurs que vous brancherez", None, QApplication.UnicodeUTF8)
        self.namesEmptyTip=QApplication.translate("MainWindow", "<br />Cliquez sur ce bouton pour préparer une liste de noms afin de renommer les prochains baladeurs que vous brancherez", None, QApplication.UnicodeUTF8)
        self.namesDialog=choixEleves.choixElevesDialog(parent =self)
        self.recentConnect="" # chemin dbus pour un baladeur récemment connecté
        # initialise deux icônes
        self.initRedoStuff()
        # initialise le tableau
        self.t=self.ui.tableView
        self.proxy=QSortFilterProxyModel()
        self.proxy.setSourceModel(self.t.model())
        self.applyPreferences()
        self.updateButtons()
        self.setAvailableNames(False)
        self.operations=[] # liste des opérations précédemment "réussies"
        self.oldThreads=set() # threads lancés éventuellement encore vivants
        QObject.connect(self.ui.helpButton, SIGNAL("clicked()"), self.help)
        QObject.connect(self.ui.umountButton, SIGNAL("clicked()"), self.umount)
        QObject.connect(self.ui.toButton, SIGNAL("clicked()"), self.copyTo)
        QObject.connect(self.ui.fromButton, SIGNAL("clicked()"), self.copyFrom)
        QObject.connect(self.ui.delButton, SIGNAL("clicked()"), self.delFiles)
        QObject.connect(self.ui.redoButton, SIGNAL("clicked()"), self.redoCmd)
        QObject.connect(self.ui.namesButton, SIGNAL("clicked()"), self.namesCmd)
        QObject.connect(self.ui.preferenceButton, SIGNAL("clicked()"), self.preference)
        QObject.connect(self.ui.tableView, SIGNAL("doubleClicked(const QModelIndex&)"), self.tableClicked)
        QObject.connect(self,SIGNAL("checkAll()"), self.checkAll)
        QObject.connect(self,SIGNAL("checkToggle()"), self.checkToggle)
        QObject.connect(self,SIGNAL("checkNone()"), self.checkNone)
        QObject.connect(self,SIGNAL("shouldNameDrive()"), self.namingADrive)
        ## accrochage d'une fonction de rappel pour les disque ajoutés
        qApp.available.addHook('object-added',   self.cbAdded())
        qApp.available.addHook('object-removed', self.cbRemoved())
        
    def checkModify(self, boolFunc):
        """
        @param boolfunc une fonction pour décider du futur état de la coche
        étant donné l'état antérieur
        Modifie les coches des baladeurs
        """
        model=self.tm
        index0=model.createIndex(0,0)
        index1=model.createIndex(len(model.donnees)-1,0)
        srange=QItemSelectionRange(index0,index1)
        for i in srange.indexes():
            checked=i.model().data(i,Qt.DisplayRole).toBool()
            model.setData(i, boolFunc(checked),Qt.EditRole)

    def checkAll(self):
        """
        Coche tous les baladeurs
        """
        self.checkModify(lambda x: True)
        
    def checkToggle(self):
        """
        Inverse la coche des baladeurs
        """
        self.checkModify(lambda x: not x)
       
    def checkNone(self):
        """
        Décoche tous les baladeurs
        """
        self.checkModify(lambda x: False)

    def namingADrive(self):
        """
        Gère un dialogue pour renommer un baladeur désigné par
        self.recentConnect
        """
        if self.availableNames:
            if self.recentConnect not in qApp.available.targets:
                return
            disk=qApp.available.targets[self.recentConnect]
            hint=db.readStudent(disk.serial, disk.uuid, ownedUsbDisk.tattooInDir(disk.mp))
            if hint != None:
                oldName=hint
            else:
                oldName=""
            d=nameAdrive.nameAdriveDialog(self, oldName=oldName,
                                          nameList=self.namesDialog.itemStrings(),
                                          driveIdent=(stickId, uuid, tattoo))
            d.show()
            result=d.exec_()
        return

    def cbAdded(self):
        """
        Renvoie une fonction de rappel pour l'abonnement aux évènements de l'arrière-boutique.
        Il s'agit de la fonction pour les disques branchés
        """
        def _cbAdded(man, obj):
            if qApp.available.modified:
                path=safePath(obj)
                self.recentConnect=str(path)
                delai=0.5 # petit délai pour que targets soit à jour
                QTimer.singleShot(delai, self.deviceAdded) 
                qApp.available.modified=False
        return _cbAdded
    
    def cbRemoved(self):
        """
        Renvoie une fonction de rappel pour l'abonnement aux évènements de l'arrière-boutique.
        Il s'agit de la fonction pour les disques débranchés
        """
        def _cbRemoved(man, obj):
            if qApp.available.modified:
                path=safePath(obj)
                if path in qApp.available.targets:
                    self.recentDisConnect=path
                    delai=0.5 # petit délai pour que targets soit à jour
                    QTimer.singleShot(delai, self.deviceRemoved)
                qApp.available.modified=False
        return _cbRemoved
    
    def deviceAdded(self):
        """
        Fonction de rappel pour un medium ajouté ; se base sur la valeur de self.recentConnect
        """
        if self.recentConnect not in qApp.available.targets:
            return
        disk=qApp.available.targets[self.recentConnect]
        if disk.parent: # c'est une partition
            QTimer.singleShot(0, self.namingADrive)
            self.findAllDisks()
            
    def deviceRemoved(self):
        """
        fonction de rappel pour un medium retiré ; se base sur la valeur de self.recentDisConnect
        """
        self.findAllDisks()
        
    def initRedoStuff(self):
        """
        Initialise des données pour le bouton central (refaire/stopper)
        """
        # réserve les icônes
        self.iconRedo = QIcon()
        self.iconRedo.addPixmap(QPixmap("/usr/share/icons/Tango/scalable/actions/go-jump.svg"), QIcon.Normal, QIcon.Off)
        self.iconStop = QIcon()
        self.iconStop.addPixmap(QPixmap("/usr/share/icons/Tango/scalable/actions/stop.svg"), QIcon.Normal, QIcon.Off)
        # réserve les phrases d'aide
        self.redoToolTip=QApplication.translate("MainWindow", "Refaire à nouveau", None, QApplication.UnicodeUTF8)
        self.redoStatusTip=QApplication.translate("MainWindow", "Refaire à nouveau la dernière opération réussie, avec les baladeurs connectés plus récemment", None, QApplication.UnicodeUTF8)
        self.stopToolTip=QApplication.translate("MainWindow", "Arrêter les opérations en cours", None, QApplication.UnicodeUTF8)
        self.stopStatusTip=QApplication.translate("MainWindow", "Essaie d'arrêter les opérations en cours. À faire seulement si celles-ci durent trop longtemps", None, QApplication.UnicodeUTF8)

    def applyPreferences(self):
        """
        Applique les préférences et les options de ligne de commande
        """
        prefs=db.readPrefs()
        self.schoolFile=prefs["schoolFile"]
        self.workdir=prefs["workdir"]
        self.refreshEnabled=prefs["refreshEnabled"]
        self.refreshDelay=prefs["refreshDelay"]
        self.manFileLocation=prefs["manfile"]
        self.mv=prefs["mv"]
        self.header=ownedUsbDisk.uDisk2.headers()
        self.findAllDisks()
        return

    def findAllDisks(self, other=None):
        """
        Initialisation du catalogue des disques USB connectés, et
        maintenance de l'interface graphique.
        @param other un catalogue déjà tout prêt de disques (None par défaut)
        """
        if other:
            qApp.available=other
        else:
            qApp.available=ownedUsbDisk.Available(access="firstFat")
        self.connectTableModel(qApp.available)
        connectedCount=int(qApp.available)
        self.ui.lcdNumber.display(connectedCount)
        self.t.resizeColumnsToContents()
        self.updateButtons()
        return
        
    def changeWd(self, newDir):
        """
        change le répertoire par défaut contenant les fichiers de travail
        @param newDir le nouveau nom de répertoire
        """
        self.workdir=newDir
        db.setWd(newDir)

    def tableClicked(self, idx):
        """
        fonction de rappel pour un double clic sur un élément de la table
        @param idx un QModelIndex
        """
        c=idx.column()
        mappedIdx=self.proxy.mapFromSource(idx)
        r=mappedIdx.row()
        h=self.header[c]
        if c==0:
            self.manageCheckBoxes()
            pass
        elif c==1:
            # case du propriétaire
            self.editOwner(mappedIdx)
        elif "mp" in h:
            cmd="xdg-open '%s'" %idx.data().toString ()
            subprocess.call(cmd, shell=True)
        elif "capacity" in h:
            mount=idx.model().partition(idx).mountPoint()
            dev,total,used,remain,pcent,path = self.diskSizeData(mount)
            pcent=int(pcent[:-1])
            w=diskFull.mainWindow(self,pcent,title=path, total=total, used=used)
            w.show()
        else:
            QMessageBox.warning(None,
                                QApplication.translate("Dialog","Double-clic non pris en compte",None, QApplication.UnicodeUTF8),
                                QApplication.translate("Dialog","pas d'action pour l'attribut {a}",None, QApplication.UnicodeUTF8).format(a=h))

    def manageCheckBoxes(self):
        """
        ouvre un dialogue pour permettre de gérer les cases à cocher globalement
        """
        cbDialog=checkBoxDialog.CheckBoxDialog(self)
        cbDialog.exec_()
        
    def diskSizeData(self, rowOrDev):
        """
        @param rowOrDev a row number in the tableView, or a device string
        @return a tuple dev,total,used,remain,pcent,path for the
        disk in the given row of the tableView
        (the tuple comes from the command df)
        """
        if type(rowOrDev)==type(0):
            path=qApp.available[rowOrDev][self.header.index("1mp")]
        else:
            path=rowOrDev
        cmd ="df '%s'" %path
        dfOutput=subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
        dfOutput=str(dfOutput.split(b"\n")[-2])
        m = re.match("(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+).*", dfOutput).groups()
        return m


    def diskFromOwner(self,student):
        """
        trouve le disque qui correspond à un propriétaire, ou alors
        renvoie le premier disque inconnu.
        @param student le propriétaire du disque
        @return le disque correspondant à l'étudiant
        """
        defaultDisk=None
        for d in ownedUsbDisk.Available(access="firstFat"):
            s=db.readStudent(d.stickid, d.uuid, d.tattoo())
            if s==student :
                return d
            elif s==None and defaultDisk==None : 
                # premier disque inconnu
                defaultDisk=d
        return defaultDisk

        
    def editOwner(self, idx):
        """
        Édition du propriétaire d'une clé.
        @param idx un QModelIndex qui pointe sur le propriétaire d'une clé
        """
        student="%s" %self.tm.data(idx,Qt.DisplayRole).toString()
        # on fait une modification dans la base de donnée des propriétaires de clés
        ownedUsbDisk.editRecord(self.diskFromOwner(student), hint=student)
        # après quoi on relit brutalement toute la list des clés connectées
        self.findAllDisks()

    def setAvailableNames(self, available):
        """
        Met à jour l'icône qui reflète la disponibilité de noms pour
        renommer automatiquement des baladeurs
        @param available vrai s'il y a des noms disponibles pour
        renommer des baladeurs.
        """
        self.availableNames=available
        if available:
            icon=self.namesFullIcon
            msg=self.namesFullTip
        else:
            icon=self.namesEmptyIcon
            msg=self.namesEmptyTip
        self.ui.namesButton.setIcon(icon)
        self.ui.namesButton.setToolTip(msg)
        self.ui.namesButton.setStatusTip(msg.replace("<br />",""))
        
    def updateButtons(self):
        """
        Désactive ou active les flèches selon que l'option correspondante
        est possible ou non. Pour les flèches : ça aurait du sens de préparer
        une opération de copie avant même de brancher des clés, donc on les
        active. Par contre démonter les clés quand elles sont absentes ça
        n'a pas d'utilité.
        Change l'icône du dialogue des noms selon qu'il reste ou non des
        noms disponibles dans le dialogue des noms.
        """
        global activeThreads, lastCommand
        active = len(qApp.available)>0
        for button in (self.ui.toButton,
                       self.ui.fromButton,
                       self.ui.delButton,
                       self.ui.umountButton):
            button.setEnabled(active)
        #modifie l'icone copyfrom/movefrom
        if self.mv:
            self.ui.fromButton.setIcon(self.movefromIcon)
        else:
            self.ui.fromButton.setIcon(self.copyfromIcon)
        # l'état du redoButton dépend de plusieurs facteurs
        # si un thread au moins est en cours, on y affiche un STOP actif
        # sinon on y met l'icône de lastCommand, et celle-ci sera active
        # seulement s'il y a une commande déjà validée
        if len(activeThreads) > 0:
            self.ui.redoButton.setIcon(self.iconStop)
            self.ui.redoButton.setToolTip(self.stopToolTip)
            self.ui.redoButton.setStatusTip(self.stopStatusTip)
            self.ui.redoButton.setEnabled(True)
        else:
            self.oldThreads=set() # vide l'ensemble puisque tout est fini
            self.ui.redoButton.setIcon(self.iconRedo)
            self.ui.redoButton.setToolTip(self.redoToolTip)
            self.ui.redoButton.setStatusTip(self.redoStatusTip)
            self.ui.redoButton.setEnabled(lastCommand!=None)
        l=self.namesDialog.ui.listWidget.findItems("*",Qt.MatchWildcard)
        if len(l)>0:
            self.ui.namesButton.setIcon(self.namesFullIcon)
        else:
            self.ui.namesButton.setIcon(self.namesEmptyIcon)

    def preference(self):
        """
        lance le dialogue des préférences
        """
        pref=preferences.preferenceWindow()
        pref.setValues(db.readPrefs())
        pref.show()
        pref.exec_()
        if pref.result()==QDialog.Accepted:
            db.writePrefs(pref.values())
            # on applique les préférences tout de suite sans redémarrer
            self.applyPreferences()

    def delFiles(self):
        """
        Lance l'action de supprimer des fichiers ou des répertoires dans les clés USB
        """
        titre1=QApplication.translate("Dialog","Choix de fichiers à supprimer",None, QApplication.UnicodeUTF8)
        titre2=QApplication.translate("Dialog","Choix de fichiers à supprimer (jokers autorisés)",None, QApplication.UnicodeUTF8)
        d=chooseInSticks.chooseDialog(self, titre1, titre2)
        ok = d.exec_()
        if ok:
            pathList=d.pathList()
            buttons=QMessageBox.Ok|QMessageBox.Cancel
            defaultButton=QMessageBox.Cancel
            reply=QMessageBox.warning(
                None,
                QApplication.translate("Dialog","Vous allez effacer plusieurs baladeurs",None, QApplication.UnicodeUTF8),
                QApplication.translate("Dialog","Etes-vous certain de vouloir effacer : "+"\n".join(pathList),None, QApplication.UnicodeUTF8),
                buttons, defaultButton)
            if reply == QMessageBox.Ok:
                cmd="usbThread.threadDeleteInUSB(p,{paths},subdir='Travail', logfile='{log}', parent=self.tm)".format(paths=pathList,log=logFileName)
                for p in qApp.available:
                    if not p.selected: continue # pas les médias désélectionnés
                    registerCmd(cmd,p)
                    t=eval(cmd)
                    t.setDaemon(True)
                    t.start()
                    self.oldThreads.add(t)
            return True
        else:
            msgBox=QMessageBox.warning(
                None,
                QApplication.translate("Dialog","Aucun fichier sélectionné",None, QApplication.UnicodeUTF8),
                QApplication.translate("Dialog","Veuillez choisir au moins un fichier",None, QApplication.UnicodeUTF8))
            return True

    def copyTo(self):
        """
        Lance l'action de copier vers les clés USB
        """
        d=copyToDialog1.copyToDialog1(parent=self, workdir=self.workdir)
        d.exec_()
        if d.ok==True:
            cmd="usbThread.threadCopyToUSB(p,{selected},subdir='{subdir}', logfile='{logfile}', parent=self.tm)".format(selected=list(d.selectedList()), subdir=self.workdir, logfile=logFileName)
            ## !!!!!!!!!!!!!!!!! itérations dans qApp.available à revoir !
            for p in qApp.available:
                if not p.selected: continue # pas les médias désélectionnés
                registerCmd(cmd,p)
                t=eval(cmd)
                t.setDaemon(True)
                t.start()
                self.oldThreads.add(t)
            return True
        else:
            msgBox=QMessageBox.warning(
                None,
                QApplication.translate("Dialog","Aucun fichier sélectionné",None, QApplication.UnicodeUTF8),
                QApplication.translate("Dialog","Veuillez choisir au moins un fichier",None, QApplication.UnicodeUTF8))
            return True

    def copyFrom(self):
        """
        Lance l'action de copier depuis les clés USB
        """
        titre1=QApplication.translate("Dialog","Choix de fichiers à copier",None, QApplication.UnicodeUTF8)
        titre2=QApplication.translate("Dialog", "Choix de fichiers à copier depuis les baladeurs", None, QApplication.UnicodeUTF8)
        okPrompt=QApplication.translate("Dialog", "Choix de la destination ...", None, QApplication.UnicodeUTF8)
        d=chooseInSticks.chooseDialog(self, title1=titre1, title2=titre2, okPrompt=okPrompt)
        d.exec_()
        if not d.ok :
            msgBox=QMessageBox.warning(None,
                                       QApplication.translate("Dialog","Aucun fichier sélectionné",None, QApplication.UnicodeUTF8),
                                       QApplication.translate("Dialog","Veuillez choisir au moins un fichier",None, QApplication.UnicodeUTF8))
            return True
        # bon, alors c'est OK pour le choix des fichiers à envoyer
        pathList=d.pathList()
        mp=d.selectedDiskMountPoint()
        initialPath=os.path.expanduser("~")
        destDir = QFileDialog.getExistingDirectory(
            None,
            QApplication.translate("Dialog","Choisir un répertoire de destination",None, QApplication.UnicodeUTF8),
            initialPath)
        if destDir and len(destDir)>0 :
            if self.mv:
                cmd="""usbThread.threadMoveFromUSB(
                           p,{paths},subdir=self.workdir,
                           rootPath='{mp}', dest='{dest}', logfile='{log}',
                           parent=self.tm)""".format(paths=pathList, mp=mp, dest=destDir, log=logFileName)
            else:
                cmd="""usbThread.threadCopyFromUSB(
                           p,{paths},subdir=self.workdir,
                           rootPath='{mp}', dest='{dest}', logfile='{log}',
                           parent=self.tm)""".format(paths=pathList, mp=mp, dest=destDir, log=logFileName)
                
            for p in qApp.available:
                if not p.selected: continue # pas les médias désélectionnés
                # on devrait vérifier s'il y a des données à copier
                # et s'il n'y en a pas, ajouter des lignes au journal
                # mais on va laisser faire ça dans le thread
                # inconvénient : ça crée quelquefois des sous-répertoires
                # vides inutiles dans le répertoire de destination.
                registerCmd(cmd,p)
                t=eval(cmd)
                t.setDaemon(True)
                t.start()
                self.oldThreads.add(t)
            # on ouvre un gestionnaire de fichiers pour voir le résultat
            buttons=QMessageBox.Ok|QMessageBox.Cancel
            defaultButton=QMessageBox.Cancel
            if QMessageBox.question(
                None,
                QApplication.translate("Dialog","Voir les copies",None, QApplication.UnicodeUTF8),
                QApplication.translate("Dialog","Voulez-vous voir les fichiers copiés ?",None, QApplication.UnicodeUTF8),
                buttons, defaultButton)==QMessageBox.Ok:
                subprocess.call("xdg-open '%s'" %destDir,shell=True)
            return True
        else:
            msgBox=QMessageBox.warning(
                None,
                QApplication.translate("Dialog","Destination manquante",None, QApplication.UnicodeUTF8),
                QApplication.translate("Dialog","Veuillez choisir une destination pour la copie des fichiers",None, QApplication.UnicodeUTF8))
            return True

    def redoCmd(self):
        """
        Relance la dernière commande, mais en l'appliquant seulement aux
        baladeurs nouvellement branchés.
        """
        global lastCommand, pastCommands, activeThreads
        if len(activeThreads)>0:
            for thread in self.oldThreads:
                if thread.isAlive():
                    try:
                        thread._Thread__stop()
                        print (str(thread.getName()) + ' is terminated')
                    except:
                        print (str(thread.getName()) + ' could not be terminated')
        else:
            if lastCommand==None:
                return
            if QMessageBox.question(
                None,
                QApplication.translate("Dialog","Réitérer la dernière commande",None, QApplication.UnicodeUTF8),
                QApplication.translate("Dialog","La dernière commande était<br>{cmd}<br>Voulez-vous la relancer avec les nouveaux baladeurs ?",None, QApplication.UnicodeUTF8).format(cmd=lastCommand))==QMessageBox.Cancel:
                return
            for p in qApp.available:
                if p.owner in pastCommands[lastCommand] : continue
                exec(compile(lastCommand,'<string>','exec'))
                t.setDaemon(True)
                t.start()
                self.oldThreads.add(t)
                pastCommands[lastCommand].append(p.owner)

    def namesCmd(self):
        """
        montre le dialogue de choix de nouveaux noms à partir d'un
        fichier administratif.
        """
        self.namesDialog.show()

    def help(self):
        """
        Affiche le widget d'aide
        """
        w=help.helpWindow(self)
        w.show()
        w.exec_()

    def umount(self):
        """
        Démonte et détache les clés USB affichées
        """
        buttons=QMessageBox.Ok|QMessageBox.Cancel
        defaultButton=QMessageBox.Cancel
        button=QMessageBox.question (
            self,
            QApplication.translate("Main","Démontage des baladeurs",None, QApplication.UnicodeUTF8),
            QApplication.translate("Main","Êtes-vous sûr de vouloir démonter tous les baladeurs cochés de la liste ?",None, QApplication.UnicodeUTF8),
            buttons,defaultButton)
        if button!=QMessageBox.Ok:
            return
        for d in qApp.available.disks_ud():
            for partition in qApp.available.parts_ud(d.path):
                cmd="umount {0}".format(partition.mp)
                subprocess.call(cmd, shell=True)
            cmd= "udisks --detach {0}".format(d.devStuff)
            subprocess.call(cmd, shell=True)
        self.findAllDisks()     # remet à jour le compte de disques
        self.operations=[] # remet à zéro la liste des opérations
                

    def connectTableModel(self, data):
        """
        Connecte le modèle de table à la table
        @param data les données de la table
        """
        self.visibleheader=[]
        for h in self.header:
            if h in ownedUsbDisk.uDisk2._itemNames:
                self.visibleheader.append(self.tr(ownedUsbDisk.uDisk2._itemNames[h]))
            else:
                self.visibleheader.append(h)
        self.tm=usbTableModel(self, self.visibleheader, data)
        self.t.setModel(self.tm)
        self.t.setItemDelegateForColumn(0, CheckBoxDelegate(self))
        self.t.setItemDelegateForColumn(1, UsbDiskDelegate(self))
        self.t.setItemDelegateForColumn(3, DiskSizeDelegate(self))
        self.proxy.setSourceModel(self.t.model())

        
    def sameDiskData(self, one, two):
        """
        @return True si les ensembles de uniqueId de one et two sont identiques
        """
        print ("GRRR one=", one)
        print ("GRRR two=", two)
        return len(one.targets) == len(two.targets) and \
            set([p.uniqueId() for p in one]) == set([p.uniqueId() for p in two])

class usbTableModel(QAbstractTableModel):
    """
    Un modèle de table pour des séries de clés USB
    """

    def __init__(self, parent=None, header=[], donnees=None):
        """
        @param parent un QObject
        @param header les en-têtes de colonnes
        @param donnees les données
        """
        QAbstractTableModel.__init__(self,parent)
        self.header=header
        self.donnees=donnees
        self.pere=parent
        self.connect(self, SIGNAL("pushCmd(QString, QString)"), self.pushCmd)
        self.connect(self, SIGNAL("popCmd(QString, QString)"), self.popCmd)

    def pushCmd(self,owner,cmd):
        """
        fonction de rappel déclenchée par les threads (au commencement)
        @param owner le propriétaire du baladeur associé au thread
        @param cmd la commande shell effectuée sur ce baladeur
        """
        global activeThreads, pastCommands, lastCommand
        owner="%s" %owner
        if owner in activeThreads:
            activeThreads[owner].append(cmd)
        else:
            activeThreads[owner]=[cmd]
        self.updateOwnerColumn()
        self.pere.updateButtons()

    def popCmd(self,owner, cmd):
        """
        fonction de rappel déclenchée par les threads (à la fin)
        @param owner le propriétaire du baladeur associé au thread
        @param cmd la commande shell effectuée sur ce baladeur
        """
        global activeThreads, pastCommands, lastCommand
        owner="%s" %owner
        owner=owner.encode("utf-8")
        if owner in activeThreads:
            cmd0=activeThreads[owner].pop()
            if cmd0 in cmd:
                msg=cmd.replace(cmd0,"")+"\n"
                logFile=open(os.path.expanduser(logFileName),"a")
                logFile.write(msg)
                logFile.close()
            else:
                raise Exception(("mismatched commands\n%s\n%s" %(cmd,cmd0)))
            if len(activeThreads[owner])==0:
                activeThreads.pop(owner)
        else:
            raise Exception("End of command without a begin.")
        self.updateOwnerColumn()
        if len(activeThreads)==0 :
            self.pere.updateButtons()

    def updateOwnerColumn(self):
        """
        force la mise à jour de la colonne des propriétaires
        """
        column=1
        self.emit(SIGNAL("dataChanged(QModelIndex, QModelIndex)"), self.index(0,column), self.index(len(self.donnees)-1, column))
        self.pere.t.viewport().update()

    def rowCount(self, parent):
        """
        @parent un QModelIndex
        """
        return len(self.donnees)
    
    def columnCount(self, parent): 
        """
        @parent un QModelIndex
        """
        return len(self.header) 

    def setData(self, index, value, role):
        if index.column()==0:
            self.donnees[index.row()].selected=value
            return True
        else:
            return QAbstractTableModel.setData(self, index, role)

    def partition(self, index):
        """
        @param index in QModelIndex
        @return la partition pointée par index
        """
        return self.donnees[index.row()][-1]
        
    def data(self, index, role): 
        if not index.isValid(): 
            return QVariant()
        elif role==Qt.ToolTipRole:
            c=index.column()
            h=self.pere.header[c]
            if c==0:
                return QApplication.translate("Main","Cocher ou décocher cette case en cliquant.<br><b>Double-clic</b> pour agir sur plusieurs baladeurs.",None, QApplication.UnicodeUTF8)
            elif c==1:
                return QApplication.translate("Main","Propriétaire de la clé USB ou du baladeur ;<br><b>Double-clic</b> pour modifier.",None, QApplication.UnicodeUTF8)
            elif "mp" in h:
                return QApplication.translate("Main","Point de montage de la clé USB ou du baladeur ;<br><b>Double-clic</b> pour voir les fichiers.",None, QApplication.UnicodeUTF8)
            elif "capacity" in h:
                return QApplication.translate("Main","Capacité de la clé USB ou du baladeur en kO ;<br><b>Double-clic</b> pour voir la place occupée.",None, QApplication.UnicodeUTF8)
            elif "vendor" in h:
                return QApplication.translate("Main","Fabricant de la clé USB ou du baladeur.",None, QApplication.UnicodeUTF8)
            elif "model" in h:
                return QApplication.translate("Main","Modèle de la clé USB ou du baladeur.",None, QApplication.UnicodeUTF8)
            elif "stickid" in h:
                return QApplication.translate("Main","Numéro de série de la clé USB ou du baladeur.",None, QApplication.UnicodeUTF8)
            else:
                return ""
        elif role != Qt.DisplayRole: 
            return QVariant()
        if index.row()<len(self.donnees):
            try:
                return QVariant(self.donnees[index.row()][index.column()])
            except KeyError:
                print("Le bug du retrait de clé non détecté a encore frappé, quand sera-t-il éliminé ?")
                self.pere.findAllDisks()
                return QVariant("")
                    
        else:
            return QVariant()

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.header[section])
        elif orientation == Qt.Vertical and role == Qt.DisplayRole:
            return QVariant(section+1)
        return QVariant()

    def sort(self, Ncol, order=Qt.DescendingOrder):
        """Sort table by given column number.
        @param Ncol numéro de la colonne de tri
        @param order l'odre de tri, Qt.DescendingOrder par défaut
        """
        self.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.donnees = sorted(self.donnees, key=operator.itemgetter(Ncol))        
        if order == Qt.DescendingOrder:
            self.donnees.reverse()
        self.emit(SIGNAL("layoutChanged()"))

def CheckBoxRect(view_item_style_options):
    """
    @param view_item_style_options des options permettant de décider de
    la taille d'un rectangle
    @return un QRect dimensionné selon les bonnes options
    """
    check_box_style_option=QStyleOptionButton()
    check_box_rect = QApplication.style().subElementRect(QStyle.SE_CheckBoxIndicator,check_box_style_option)
    check_box_point=QPoint(view_item_style_options.rect.x() + view_item_style_options.rect.width() / 2 - check_box_rect.width() / 2, view_item_style_options.rect.y() + view_item_style_options.rect.height() / 2 - check_box_rect.height() / 2)
    return QRect(check_box_point, check_box_rect.size())

class CheckBoxDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        QStyledItemDelegate.__init__(self,parent)

    def paint(self, painter, option, index):
        checked = index.model().data(index, Qt.DisplayRole).toBool()
        check_box_style_option=QStyleOptionButton()
        check_box_style_option.state |= QStyle.State_Enabled
        if checked:
            check_box_style_option.state |= QStyle.State_On
        else:
            check_box_style_option.state |= QStyle.State_Off
        check_box_style_option.rect = CheckBoxRect(option);
        QApplication.style().drawControl(QStyle.CE_CheckBox, check_box_style_option, painter)

    def editorEvent(self, event, model, option, index):
        if ((event.type() == QEvent.MouseButtonRelease) or (event.type() == QEvent.MouseButtonDblClick)):
            if (event.button() != Qt.LeftButton or not CheckBoxRect(option).contains(event.pos())):
                return False
            if (event.type() == QEvent.MouseButtonDblClick):
                return True
        elif (event.type() == QEvent.KeyPress):
            if event.key() != Qt.Key_Space and event.key() != Qt.Key_Select:
                return False
        else:
            return False
        checked = index.model().data(index, Qt.DisplayRole).toBool()
        result = model.setData(index, not checked, Qt.EditRole)
        return result

        
class UsbDiskDelegate(QStyledItemDelegate):
    """
    Classe pour identifier le baladeur dans le tableau.
    La routine de rendu à l'écran trace une petite icône et le nom du
    propriétaire à côté.
    """
    def __init__(self, parent):
        QStyledItemDelegate.__init__(self,parent)
        self.okPixmap=QPixmap("/usr/share/icons/Tango/16x16/status/weather-clear.png")
        self.busyPixmap=QPixmap("/usr/share/icons/Tango/16x16/actions/view-refresh.png")

    def paint(self, painter, option, index):
        global activeThreads
        text = index.model().data(index, Qt.DisplayRole).toString()
        rect0=QRect(option.rect)
        rect1=QRect(option.rect)
        h=rect0.height()
        w=rect0.width()
        rect0.setSize(QSize(h,h))
        rect1.translate(h,0)
        rect1.setSize(QSize(w-h,h))
        QApplication.style().drawItemText (painter, rect1, Qt.AlignLeft+Qt.AlignVCenter, option.palette, True, text)
        QApplication.style().drawItemText (painter, rect0, Qt.AlignCenter, option.palette, True, "O")
        text=("%s" %text).encode("utf-8")
        if text in activeThreads:
            QApplication.style().drawItemPixmap (painter, rect0, Qt.AlignCenter, self.busyPixmap)
        else:
            QApplication.style().drawItemPixmap (painter, rect0, Qt.AlignCenter, self.okPixmap)
        
class DiskSizeDelegate(QStyledItemDelegate):
    """
    Classe pour figurer la taille de la mémoire du baladeur. Trace un petit
    secteur représentant la place occupée, puis affiche la place avec l'unité
    le plus parropriée.
    """
    def __init__(self, parent):
        QStyledItemDelegate.__init__(self,parent)
        

    def paint(self, painter, option, index):
        text=index.model().data(index, Qt.DisplayRole).toString()
        if text=="":
            value=0
        else:
            value = int(index.model().data(index, Qt.DisplayRole).toString())
        text = self.val2txt(value)
        rect0=QRect(option.rect)
        rect1=QRect(option.rect)
        rect0.translate(2,(rect0.height()-16)/2)
        rect0.setSize(QSize(16,16))
        rect1.translate(20,0)
        rect1.setWidth(rect1.width()-20)
        QApplication.style().drawItemText (painter, rect1, Qt.AlignLeft+Qt.AlignVCenter, option.palette, True, text)
        # dessin d'un petit cercle pour l'occupation
        mount=index.model().partition(index).mountPoint()
        dev,total,used,remain,pcent,path = self.parent().diskSizeData(mount)
        pcent=int(pcent[:-1])
        painter.setBrush(QBrush(QColor("slateblue")))
        painter.drawPie(rect0,0,16*360*pcent/100)

    def val2txt(self, val):
        """
        @return a string with a value with unit K, M, or G
        """
        suffixes=["B", "KB", "MB", "GB", "TB"]
        val*=1.0 # calcul flottant
        i=0
        while val > 1024 and i < len(suffixes):
            i+=1
            val/=1024
        return "%4.1f %s" %(val, suffixes[i])
    
