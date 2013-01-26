# -*- coding: utf-8 -*-    
# 	$Id: ownedUsbDisk.py 47 2011-06-13 10:20:14Z georgesk $	

licence={}
licence['en']="""
    file ownedUsbDisk.py
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
import usbDisk, db
import os.path, dbus, subprocess, time
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from globaldef import markFileName

"""
liste statique pour éviter de demander chaque seconde le nom d'un
propriétaire de clé si on n'a pas souhaité le donner.
"""

def tattooInDir(mountPoint):
    """
    Renvoie le tatouage pour un point de montage donné, quitte à le créer
    si nécessaire.
    @param mountPoint un point de montage de partition
    @return le tatouage
    """
    tattooFileName = os.path.join(mountPoint,".scolasync-tattoo")
    tattoo_=""
    if os.path.exists(tattooFileName):
        tattoo_=open(tattooFileName,"r").readlines()[0].strip()
    if tattoo_ != "" :
        # le tatouage existe déjà, on renvoie sa valeur
        return tattoo_
    else:
        tattoo_="%12.2f" %time.time()
        time.sleep(0.05)
        # si on espace deux créations de tatouages de 50 millisecondes
        # il est impossible d'avoir deux tatouages identiques générés
        # par le même ordinateur. Les chances que ça arrive avec des
        # ordinateurs distincts sont minimes
        outfile=open(tattooFileName,"w")
        outfile.write(tattoo_)
        outfile.close()
        # on renvoie le nouveau tatouage
        return tattoo_

def editRecord(owd, hint=""):
    """
    édition de la base de données
    @param owd une instance de ownedUsbDisk
    @param hint chaîne vide par défaut. Peut être le nom de l'ancien propriétaire
    """
    title=QApplication.translate("Dialog", "Choix du propriétaire", None, QApplication.UnicodeUTF8)
    prompt=QApplication.translate("Dialog", "Nouveau nom du propriétaire du baladeur", None, QApplication.UnicodeUTF8)
    newStudent, ok = QInputDialog.getText(None, title, prompt, text=hint)
    if ok:
        newStudent="%s" %newStudent
        db.writeStudent(owd.stickid, owd.getFatUuid(), owd.tattoo(), newStudent)

class uDisk(usbDisk.uDisk,QObject):
    """
    une classe qui ajoute un nom de propriétaire aux disque USB,
    et qui en même temps ajoute des particularités selon le nom du
    vendeur et le modèle.
    """
    def __init__(self, path, bus, checkable=False):
        """
        @param path un chemin dans le système dbus
        @param bus un objet dbus.BusSystem
        @param checkable vrai si on fera usage de self.selected
        """
        usbDisk.uDisk.__init__(self,path, bus, checkable)
        QObject.__init__(self)
        self.owner="" # le propriétaire est déterminé plus tard
        self.vendor=self.getProp("drive-vendor")
        self.model=self.getProp("drive-model")
        self.visibleDirs=self.readQuirks()

    def uniqueId(self):
        """
        @return un identifiant unique, composé du nom du propriétaire
        suivi du tatouage
        """
        return "%s~%s" %(self.owner, self.tattoo())

    def tattoo(self):
        """
        Renvoie un tatouage présent sur la clé, quitte à le créer.
        @result un tatouage, supposément unique.
        """
        ff=self.getFirstFat()
        if ff:
            fatPath=ff.ensureMounted()
            return tattooInDir(fatPath)
        else:
            return ""
    
    def readQuirks (self):
        """
        Lit un dictionnaire indexé par le noms de vendeurs et les noms de modèle
        pour associer à ces modèles particuliers un répertoire visible.
        voir la fonction visibleDir. Ce dictionnaire est dans le fichier
        /usr/share/scolasync/marques.py ou dans ${HOME}/.scolasync/marques.py,
        (sous Linux) cette dernière place étant prépondérante.
        """
        f1="/usr/share/scolasync/marques.py"
        f2=os.path.expanduser(markFileName)
        if os.path.exists(f2):
            f=f2
        else:
            f=f1
        result=eval(open(f,"r", encoding="utf-8").read())
        return result
        
    def visibleDir(self):
        """
        Renvoie le répertoire particulier de la partition qui sera visible
        quand le baladeur est utilisé par son interface utilisateur. Ce
        répertoire peut varier selon les vendeurs et les modèles.
        """
        k=self.vendor+":"+self.model
        if k in self.visibleDirs.keys():
            return self.visibleDirs[k]
        else:
            return "."

    def headers(checkable=False,locale="C"):
        """
        Méthode statique
        renvoie des titres pour les items obtenus par __getitem__
        la deuxième colonne sera toujours le propriétaire
        @param checkable vrai si le premier en-tête correspond à une colonne de cases à cocher
        @param locale la locale, pour traduire les titres
        @return une liste de titres de colonnes
        """
        result=usbDisk.uDisk.headers(checkable, locale)
        ownerProp=QApplication.translate("uDisk","owner",None, QApplication.UnicodeUTF8)
        result.insert(1,ownerProp)
        return result

    def ownerByDb(self):
        """
        renvoie un nom de propriétaire dans tous les cas.
        """
        if self.owner != "":
            return self.owner
        else:
            s=db.readStudent(self.stickid, self.getFatUuid(), self.tattoo())
            if s != None:
                self.owner=s
                return s
            else:
                return QApplication.translate("Dialog","inconnu",None, QApplication.UnicodeUTF8)

    def __getitem__(self,n):
        """
        renvoie un élément de listage de données internes au disque
        Fait en sorte que la deuxième colonne soit toujours le propriétaire
        @param n un nombre
        @param checkable vrai si on doit renvoyer une propriété supplémentaire pour n==0
        @return si n==-1, renvoie self ; si checkable est vrai, renvoie un élément si n>0, et le drapeau self.selected si n==0 ; sinon un élément de façon ordinaire. Les noms des éléments sont dans la liste self.itemNames
        """
        propListe=usbDisk.uDisk.headers()
        if n == -1:
            return self # pour accéder à toutes les données d'une partition
        if self.checkable:
            if n==0:
                return self.selected
            elif n==1:
                return self.ownerByDb()
            elif n==2:
                return self.unNumberProp(0)
            else:
                return self.unNumberProp(n-1)
        else:
            if n==0:
                return self.unNumberProp(0)
            elif n==1:
                return self.ownerByDb()
            else:
                return self.unNumberProp(n)
    
    
    headers = staticmethod(headers)

    def ensureOwner(self, noLoop):
        """
        Demande un nom de propriétaire si celui-ci n'est pas encore défini
        pour cette clé USB
        @param noLoop si True : ne fait pas de dialogue interactif
        @return un nom de propriétaire si c'est un disque, sinon None
        """
        if self.getProp("device-is-drive") and self.isUsbDisk():
            if noLoop==False and not db.knowsId(self.stickid, self.getFatUuid(), self.tattoo()) :
                prompt=QApplication.translate("Dialog","La cle {id}<br>n'est pas identifiee, donnez le nom du proprietaire",None, QApplication.UnicodeUTF8).format(id=self.stickid)
                title=QApplication.translate("Dialog","Entrer un nom",None, QApplication.UnicodeUTF8)
                text,ok = QInputDialog.getText(None, title, prompt)
                if ok and len(text)>0 and not db.hasStudent(text):
                    db.writeStudent(self.stickid, self.getFatUuid(), self.tattoo(), text)
        return db.readStudent(self.stickid, self.getFatUuid(), self.tattoo())
        
class Available(usbDisk.Available):
    """
    Une classe qui fournit une collection de disques USB connectés,
    avec leurs propriétaires. Les propriétaires sont recensés juste
    avant le montage des partions FAT.
    """

    def __init__(self, checkable=False, access="disk", diskClass=uDisk, diskDict=None, noLoop=True):
        """
        Le constructeur est un proxy pour usbDisk.Available.__init__
        qui force la classe de disques à utiliser : en effet ici
        uDisk désigne ownedUsbDisk.uDisk
        @param checkable True si on veut pouvoir sélectionner des disques en cochant
        @param access le mode d'accès : 'disk' ou 'firstFat'
        @param diskClass la classe d'objets à créer pour chaque disque
        @param diskDict un dictionnaire des disque maintenu par deviceListener
        @param noLoop doit être True pour éviter de lancer un dialogue
        """
        self.noLoop=noLoop
        usbDisk.Available.__init__(self, checkable, access, diskClass, diskDict)
        
    def finishInit(self):
        """
        Fin de l'initialisation : trouve les propriétaires des disques
        puis identifie les partitions FAT et les monte
        """
        self.getFirstFats() # premier passage, pour repérer chaque partition FAT
        for d in self.disks.keys():
            d.owner=d.ensureOwner(self.noLoop)
        self.mountFirstFats()

if __name__=="__main__":
    machin=Available()
    print (machin)
    
