#!/usr/bin/python
# -*- coding: utf-8 -*-
# 	$Id: mainWindow.py 47 2011-06-13 10:20:14Z georgesk $	

licence={}
licence['en']="""
    file mainWindow.py
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
import ownedUsbDisk, help, copyToDialog1, chooseInSticks, usbThread
import diskFull, preferences, checkBoxDialog
import os.path, operator, subprocess, dbus, re, time, copy
from notification import Notification
import db
import deviceListener
import choixEleves
import nameAdrive
from globaldef import logFileName, _dir

# cette donnée est globale, pour être utilisé depuis n'importe quel objet
qApp.diskData=ownedUsbDisk.Available(True,access="firstFat")

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
    def __init__(self, parent, opts, locale="fr_FR"):
        """
        Le constructeur
        @param parent un QWidget
        @param opts une liste d'options extraite à l'aide de getopts
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
        self.opts=opts
        self.timer=QTimer()
        self.listener=deviceListener.DeviceListener(self)
        self.applyPreferences()
        self.updateButtons()
        self.setAvailableNames(False)
        self.operations=[] # liste des opérations précédemment "réussies"
        self.oldThreads=set() # threads lancés éventuellement encore vivants
        self.flashTimer=QTimer()
        self.flashTimer.setSingleShot(True)
        self.checkDisksLock=False # autorise self.checkDisks
        QObject.connect(self.ui.forceCheckButton, SIGNAL("clicked()"), self.checkDisks)
        QObject.connect(self.timer, SIGNAL("timeout()"), self.checkDisks)
        QObject.connect(self.flashTimer, SIGNAL("timeout()"), self.normalLCD);
        QObject.connect(self.ui.helpButton, SIGNAL("clicked()"), self.help)
        QObject.connect(self.ui.umountButton, SIGNAL("clicked()"), self.umount)
        QObject.connect(self.ui.toButton, SIGNAL("clicked()"), self.copyTo)
        QObject.connect(self.ui.fromButton, SIGNAL("clicked()"), self.copyFrom)
        QObject.connect(self.ui.delButton, SIGNAL("clicked()"), self.delFiles)
        QObject.connect(self.ui.redoButton, SIGNAL("clicked()"), self.redoCmd)
        QObject.connect(self.ui.namesButton, SIGNAL("clicked()"), self.namesCmd)
        QObject.connect(self.ui.preferenceButton, SIGNAL("clicked()"), self.preference)
        QObject.connect(self.ui.tableView, SIGNAL("doubleClicked(const QModelIndex&)"), self.tableClicked)
        QObject.connect(self,SIGNAL("deviceAdded(QString)"), self.deviceAdded)
        QObject.connect(self,SIGNAL("deviceRemoved(QString)"), self.deviceRemoved)
        QObject.connect(self,SIGNAL("checkAll()"), self.checkAll)
        QObject.connect(self,SIGNAL("checkToggle()"), self.checkToggle)
        QObject.connect(self,SIGNAL("checkNone()"), self.checkNone)
        QObject.connect(self,SIGNAL("shouldNameDrive()"), self.namingADrive)
        
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
            stickId, tattoo, uuid = self.listener.identify(self.recentConnect)
            hint=db.readStudent(stickId, uuid, tattoo)
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
    
    def deviceAdded(self, s):
        """
        fonction de rappel pour un medium ajouté
        @param s chemin UDisks, exemple : /org/freedesktop/UDisks/devices/sdb3
        """
        vfatPath = self.listener.vfatUsbPath(str(s))
        if vfatPath:
            self.recentConnect=str(s)
            # pas tout à fait équivalent à l'émission d'un signal avec emit :
            # le timer s'exécutera en dehors du thread qui appartient à DBUS !
            QTimer.singleShot(0, self.namingADrive)
        self.checkDisks(noLoop=True)
            
    def deviceRemoved(self, s):
        """
        fonction de rappel pour un medium retiré
        @param s une chaine de caractères du type /dev/sdxy
        """
        if qApp.diskData.hasDev(s):
            self.checkDisks()
        
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

    def showEvent (self, ev):
        """
        modification du comportement du widget original, pour
        démarrer le timer et les vérifications de baladeurs
        après construction de la fenêtre seulement
        """
        result=QMainWindow.showEvent(self, ev)
        self.setTimer()
        self.checkDisks(force=True) # met à jour le compte de disques affiché
        return result

    def setTimer(self, enabled=True):
        """
        sets the main timer
        """
        if self.refreshEnabled:
            self.timer.start(self.refreshDelay*1000)
        else:
            self.timer.stop()

    def applyPreferences(self):
        """
        Applique les préférences et les options de ligne de commande
        """
        prefs=db.readPrefs()
        self.schoolFile=prefs["schoolFile"]
        self.workdir=prefs["workdir"]
        self.refreshEnabled=prefs["refreshEnabled"]
        self.refreshDelay=prefs["refreshDelay"]
        self.setTimer()
        self.manFileLocation=prefs["manfile"]
        # on active les cases à cocher si ça a été réclamé par les options
        # ou par les préférences
        self.checkable=("--check","") in self.opts or ("-c","") in self.opts or prefs["checkable"]
        self.mv=prefs["mv"]
        other=ownedUsbDisk.Available(self.checkable,access="firstFat")
        qApp.diskData=other
        self.header=ownedUsbDisk.uDisk.headers(self.checkable)
        self.connectTableModel(other)
        self.updateButtons()

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
        if c==0 and self.checkable:
            self.manageCheckBoxes()
            pass
        elif c==1 or (c==0 and not self.checkable):
            # case du propriétaire
            self.editOwner(mappedIdx)
        elif "device-mount-paths" in h:
            cmd="nautilus '%s'" %idx.data().toString ()
            subprocess.call(cmd, shell=True)
        elif "device-size" in h:
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
            path=qApp.diskData[rowOrDev][self.header.index("1device-mount-paths")]
        else:
            path=rowOrDev
        cmd ="df '%s'" %path
        dfOutput=subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
        dfOutput=str(dfOutput.split(b"\n")[-2])
        m = re.match("(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+).*", dfOutput).groups()
        return m


    def diskFromOwner(self,student):
        """
        trouve le disque qui correspond à un propriétaire
        @param student le propriétaire du disque
        @return le disque correspondant à l'étudiant
        """
        found=False
        for d in qApp.diskData.disks.keys():
            if d.owner==student:
                found=True
                break
            # si on ne trouve pas avec le nom, on essaie de trouver
            # un disque encore inconnu, le premier venu
            if d.owner==None or len(d.owner)==0:
                found=True
                break
        if found:
            return d
        else:
            return None
        
    def editOwner(self, idx):
        """
        Édition du propriétaire d'une clé.
        @param idx un QModelIndex qui pointe sur le propriétaire d'une clé
        """
        student="%s" %self.tm.data(idx,Qt.DisplayRole).toString()
        ownedUsbDisk.editRecord(self.diskFromOwner(student), hint=student)
        other=ownedUsbDisk.Available(self.checkable,access="firstFat")
        qApp.diskData=other
        self.connectTableModel(other)
        self.checkDisks()

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
        active = len(qApp.diskData)>0
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
                for p in qApp.diskData:
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
            for p in qApp.diskData:
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
                
            for p in qApp.diskData:
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
            # on ouvre nautilus pour voir le résultat des copies
            buttons=QMessageBox.Ok|QMessageBox.Cancel
            defaultButton=QMessageBox.Cancel
            if QMessageBox.question(
                None,
                QApplication.translate("Dialog","Voir les copies",None, QApplication.UnicodeUTF8),
                QApplication.translate("Dialog","Voulez-vous voir les fichiers copiés ?",None, QApplication.UnicodeUTF8),
                buttons, defaultButton)==QMessageBox.Ok:
                subprocess.call("nautilus '%s'" %destDir,shell=True)
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
            for p in qApp.diskData:
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
        for d in qApp.diskData.disks.keys():
            devfile_disk=d.getProp("device-file-by-path")
            if isinstance(devfile_disk, dbus.Array):
                devfile_disk=devfile_disk[0]
            subprocess.call("eject %s 2>/dev/null || true && udisks --detach %s" %(devfile_disk,devfile_disk), shell=True)
        self.checkDisks()  # remet à jour le compte de disques
        self.operations=[] # remet à zéro la liste des opérations
                

    def connectTableModel(self, data):
        """
        Connecte le modèle de table à la table
        @param data les données de la table
        """
        self.visibleheader=[]
        for h in self.header:
            if h in ownedUsbDisk.uDisk._itemNames:
                self.visibleheader.append(self.tr(ownedUsbDisk.uDisk._itemNames[h]))
            else:
                self.visibleheader.append(h)
        self.tm=usbTableModel(self, self.visibleheader,data,self.checkable)
        self.t.setModel(self.tm)
        if self.checkable:
            self.t.setItemDelegateForColumn(0, CheckBoxDelegate(self))
            self.t.setItemDelegateForColumn(1, UsbDiskDelegate(self))
            self.t.setItemDelegateForColumn(3, DiskSizeDelegate(self))
        else:
            self.t.setItemDelegateForColumn(0, UsbDiskDelegate(self))
            self.t.setItemDelegateForColumn(2, DiskSizeDelegate(self))
        self.proxy.setSourceModel(self.t.model())

        
    def checkDisks(self, force=False, noLoop=True):
        """
        fonction relancée périodiquement pour vérifier s'il y a un changement
        dans le baladeurs, et signaler dans le tableau les threads en cours.
        Le tableau est complètement régénéré à chaque fois, ce qui n'est pas
        toujours souhaitable.
        À la fin de chaque vérification, un court flash est déclenché sur
        l'afficheur de nombre de baladeurs connectés et sa valeur est mise à
        jour.
        @param force pour forcer une mise à jour du tableau
        @param noLoop si False, on ne rentrera pas dans une boucle de Qt
        """
        if self.checkDisksLock:
            # jamais plus d'un appel à la fois pour checkDisks
            return
        self.checkDisksLock=True
        other=ownedUsbDisk.Available(
            self.checkable,
            access="firstFat",
            diskDict=self.listener.connectedVolumes,
            noLoop=noLoop)
        if force or not self.sameDiskData(qApp.diskData, other):
            qApp.diskData=other
            connectedCount=int(other)
            self.connectTableModel(other)
            self.updateButtons()
            self.t.resizeColumnsToContents()
            self.ui.lcdNumber.display(connectedCount)
        self.flashLCD()
        # met la table en ordre par la colonne des propriétaires
        if self.checkable:
            col=1
        else:
            col=0
        self.t.horizontalHeader().setSortIndicator(1, Qt.AscendingOrder);
        self.t.setSortingEnabled(True)
        self.t.resizeColumnsToContents()
        self.checkDisksLock=False


    def sameDiskData(self, one, two):
        """
        @return True si les ensembles de uniqueId de one et two sont identiques
        """
        return set([p.uniqueId() for p in one]) == set([p.uniqueId() for p in two])

    def flashLCD(self):
        """
        change le style de l'afficheur LCD pendant une fraction de seconde
        """
        self.ui.lcdNumber.setBackgroundRole(QPalette.Highlight)
        self.flashTimer.start(250) ## un quart de seconde

    def normalLCD(self):
        """
        remet le style par défaut pour l'afficheur LCD
        """
        self.ui.lcdNumber.setBackgroundRole(QPalette.Window)

class usbTableModel(QAbstractTableModel):
    """
    Un modèle de table pour des séries de clés USB
    """

    def __init__(self, parent=None, header=[], donnees=None, checkable=False):
        """
        @param parent un QObject
        @param header les en-têtes de colonnes
        @param donnees les données
        @param checkable vrai si la première colonne est composée de boîtes à cocher. Faux par défaut
        """
        QAbstractTableModel.__init__(self,parent)
        self.header=header
        self.donnees=donnees
        self.checkable=checkable
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
        owner=owner.encode("utf-8")
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
        if self.checkable:
            column=1
        else:
            column=0
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
        if index.column()==0 and self.checkable:
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
            if c==0 and self.checkable:
                return QApplication.translate("Main","Cocher ou décocher cette case en cliquant.<br><b>Double-clic</b> pour agir sur plusieurs baladeurs.",None, QApplication.UnicodeUTF8)
            elif c==1:
                return QApplication.translate("Main","Propriétaire de la clé USB ou du baladeur ;<br><b>Double-clic</b> pour modifier.",None, QApplication.UnicodeUTF8)
            elif "device-mount-paths" in h:
                return QApplication.translate("Main","Point de montage de la clé USB ou du baladeur ;<br><b>Double-clic</b> pour voir les fichiers.",None, QApplication.UnicodeUTF8)
            elif "device-size" in h:
                return QApplication.translate("Main","Capacité de la clé USB ou du baladeur en kO ;<br><b>Double-clic</b> pour voir la place occupée.",None, QApplication.UnicodeUTF8)
            elif "drive-vendor" in h:
                return QApplication.translate("Main","Fabricant de la clé USB ou du baladeur.",None, QApplication.UnicodeUTF8)
            elif "drive-model" in h:
                return QApplication.translate("Main","Modèle de la clé USB ou du baladeur.",None, QApplication.UnicodeUTF8)
            elif "drive-serial" in h:
                return QApplication.translate("Main","Numéro de série de la clé USB ou du baladeur.",None, QApplication.UnicodeUTF8)
            else:
                return ""
        elif role != Qt.DisplayRole: 
            return QVariant()
        if index.row()<len(self.donnees):
            return QVariant(self.donnees[index.row()][index.column()])
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
    
