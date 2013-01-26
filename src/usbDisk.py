# -*- coding: utf-8 -*-    
# $Id: usbDisk.py 36 2011-01-15 19:37:27Z georgesk $	

licence={}
licence_en="""
    file usbDisk.py
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

licence['en']=licence_en
dependences="python3-dbus python3-dbus.mainloop.qt"
python3safe="True"

import dbus, subprocess, os, os.path, re, time
from PyQt4.QtGui import *


class uDisk:
    """
    une classe pour représenter un disque ou une partition.

    les attributs publics sont :
    - \b path  le chemin dans le système dbus
    - \b device l'objet dbus qui correspond à l'instance
    - \b device_prop un proxy pour questionner cet objet dbus
    - \b selected booléen vrai si on doit considérer cette instance comme sélectionnée. Vrai à l'initialisation
    - \b checkable booléen vrai si on veut que la sélection puisse être modifiée par l'utilisateur dans l'interface graphique
    """

    def __init__(self, path, bus, checkable=False):
        """
        Le constructeur
        @param path un chemin dans le système dbus
        @param bus un objet dbus.BusSystem
        @param checkable vrai si on fera usage de self.selected
        """
        self.path=path
        self.mp=None # a variable to cache the result of self.mountPoint()
        self.device = bus.get_object("org.freedesktop.UDisks", self.path)
        self.device_prop = dbus.Interface(self.device, "org.freedesktop.DBus.Properties")
        self.selected=True
        self.checkable=checkable
        self.stickid=self.getProp("drive-serial")
        self.uuid=self.getProp("id-uuid")
        self.fatuuid=None  # pour l'uuid de la première partion vfat
        self.firstFat=None # poignée de la première partition vfat
        p=self.file()
        # self.devStuff is the name of device which is usable to umount safely this object
        if p:
            self.devStuff=os.path.abspath(os.path.join(os.path.dirname(p), os.readlink(p)))
        else:
            self.devStuff=None
        #

            
    _itemNames={
        "1device-mount-paths":QApplication.translate("uDisk","point de montage",None, QApplication.UnicodeUTF8),
        "2device-size":QApplication.translate("uDisk","taille",None, QApplication.UnicodeUTF8),
        "3drive-vendor":QApplication.translate("uDisk","marque",None, QApplication.UnicodeUTF8),
        "4drive-model":QApplication.translate("uDisk","modèle de disque",None, QApplication.UnicodeUTF8),
        "5drive-serial":QApplication.translate("uDisk","numéro de série",None, QApplication.UnicodeUTF8),
        }

    _specialItems={"0Check":QApplication.translate("uDisk","cocher",None, QApplication.UnicodeUTF8)}

    _ItemPattern=re.compile("[0-9]?(.*)")
    
    def getFatUuid(self):
        """
        renvoie l'uuid de la première partition FAT après que celle-ci aura été
        identifiée (utile pour les disques partitionnés)
        @return un uuid
        """
        return "%s" %self.fatuuid
        
    def uniqueId(self):
        """
        renvoie un identifiant unique. Dans cette classe, cette fonction
        est synonyme de file()
        @return un identifiant unique, garanti par le système de fichiers
        """
        return self.file()
        
    def headers(checkable=False,locale="C"):
        """
        Méthode statique, pour avoir des titres de colonne.
        renvoie des titres pour les items obtenus par __getitem__. Le
        résultat dépend du paramètre checkable.
        @param checkable vrai si le premier en-tête correspond à une colonne de cases à cocher
        @param locale la locale, pour traduire les titres éventuellement.
        Valeur par défaut : "C"
        @return une liste de titres de colonnes
        """
        if checkable:
            result= list(uDisk._specialItems.keys())+ list(uDisk._itemNames.keys())
            return sorted(result)
        else:
            return sorted(uDisk._itemNames.keys())
        
    headers = staticmethod(headers)
    
    def devicePropProxy(self, bus):
        """
        renvoie un proxy vers un navigateur de propriétés
        @param bus une instace de dbus.SystemBus
        @return l'objet proxy
        """
        return self.device_prop

    def isTrue(self,prop, value=None):
        """
        Renvoie la valeur de vérité d'une propriété
        @param prop une propriété
        @param value
        @return vrai si la propriété est vraie (cas où value==None) ou vrai si la propriété a exactement la valeur value.
        """
        if value==None:
            return  bool(self.getProp(prop))
        else:
            return self.getProp(prop)==value
    
    def isUsbDisk(self):
        """
        Facilite le réprage des disques USB USB
        @return vrai dans le cas d'un disque USB
        """
        return self.isTrue("device-is-removable") and self.isTrue("drive-connection-interface","usb") and self.isTrue("device-size")

    def __str__(self):
        """
        Fournit une représentation imprimable
        @return une représentation imprimable de l'instance
        """
        return self.title()+self.valuableProperties()

    def title(self):
        """
        Permet d'obtenir un identifiant unique de disque
        @return le chemin dbus de l'instance
        """
        return self.path

    def file(self):
        """
        Permet d'accèder à l'instance par un nom de fichier
        @return un nom valide dans le système de fichiers, pour accéder
        à l'instance.
        """
        fileByPath=self.getProp("device-file-by-path")
        if isinstance(fileByPath, dbus.Array) and len(fileByPath)>0:
            fileByPath=fileByPath[0]
            return fileByPath
        else:
            return None
    
    def mountPoint(self):
        """
        Permet d'accèder à l'instance par un point de montage
        @return un point de montage, s'il en existe, sinon None
        """
        if self.mp==None:
            paths=self.getProp("device-mount-paths")
            if isinstance(paths, dbus.Array) and len(paths)>0:
                self.mp=paths[0]
                return paths[0]
            else:
                return None
        else:
            return self.mp
    
    def getProp(self, name):
        """
        Facilite l'accès aux propriétés à l'aide des mots clés du module udisks
        @param name le nom d'une propriété
        @return une propriété dbus du disque ou de la partition, sinon None si le nom name est illégal
        """
        try:
            return self.device_prop.Get("org.freedesktop.UDisks", name)
        except:
            return None

    def isDosFat(self):
        """
        Permet de reconnaitre les partitions DOS-FAT
        @return True dans le cas d'une partition FAT16 ou FAT32
        """
        return self.getProp("id-type")=="vfat"

    def isMounted(self):
        """
        @return True si le disque ou la partion est montée
        """
        return bool(self.getProp("device-is-mounted"))
        
    def valuableProperties(self,indent=4):
        """
        Facilite l'accès aux propriétés intéressantes d'une instance
        @return une chaîne indentée avec les propriétés intéressantes, une par ligne
        """
        prefix="\n"+" "*indent
        r=""
        props=["device-file-by-id",
               "device-file-by-path",
               "device-mount-paths",
               "device-is-partition-table",
               "partition-table-count",
               "device-is-read-only",
               "device-is-drive",
               "device-is-optical-disc",
               "device-is-mounted",
               "drive-vendor",
               "drive-model",
               "drive-serial",
               "id-uuid",
               "partition-slave",
               "partition-type",
               "device-size",
               "id-type"]
        for prop in props:
            p=self.getProp(prop)
            if isinstance(p,dbus.Array):
                if len(p)>0:
                    r+=prefix+"%s = array:" %(prop)
                    for s in p:
                        r+=prefix+" "*indent+s
            elif isinstance(p,dbus.Boolean):
                r+=prefix+"%s = %s" %(prop, bool(p))
            elif isinstance(p,dbus.Int16) or isinstance(p,dbus.Int32) or isinstance(p,dbus.Int64) or isinstance(p,dbus.UInt16) or isinstance(p,dbus.UInt32) or isinstance(p,dbus.UInt64) or isinstance(p,int):
                if p < 10*1024:
                    r+=prefix+"%s = %s" %(prop,p)
                elif p < 10*1024*1024:
                    r+=prefix+"%s = %s k" %(prop,p/1024)
                elif p < 10*1024*1024*1024:
                    r+=prefix+"%s = %s M" %(prop,p/1024/1024)
                else:
                    r+=prefix+"%s = %s G" %(prop,p/1024/1024/1024)
            else:
                r+=prefix+"%s = %s" %(prop,p)
        r+=prefix+"%s = %s" %('devStuff', self.devStuff)
        return r

    def master(self):
        """
        renvoie le chemin du disque, dans le cas où self est une partition
        @return le chemin dbus du disque maître, sinon "/"
        """
        return self.getProp("partition-slave")

    def unNumberProp(self,n):
        """
        retire le numéro des en-têtes pour en faire un nom de propriété
        valide pour interroger dbus
        @param n un numéro de propriété qui se réfère aux headers
        @return une propriété renvoyée par dbus, dans un format imprimable
        """
        m=uDisk._ItemPattern.match(self.headers()[n])
        try:
            prop=m.group(1)
            result=self.showableProp(prop)
            return result
        except:
            return ""
        
    def __getitem__(self,n):
        """
        Renvoie un élément de listage de données internes au disque
        @param n un nombre
        @param checkable vrai si on doit renvoyer une propriété supplémentaire pour n==0
        @return si checkable est vrai, un élément si n>0, et le drapeau self.selected si n==0 ; sinon un élément de façon ordinaire. Les noms des éléments sont dans la liste itemNames utilisée dans la fonction statique headers
        """
        propListe=self.headers()
        if self.checkable:
            if n==0:
                return self.selected
            elif n <= len(propListe):
                return self.unNumberProp(n-1)
        else:
            if n < len(propListe):
                return self.unNumberProp(n)

    def showableProp(self, name):
        """
        Renvoie une propriété dans un type "montrable" par QT.
        les propriétés que renvoie dbus ont des types inconnus de Qt4,
        cette fonction les transtype pour que QVariant arrive à les
        prendre en compte.
        @param name le nom de la propriété
        @return une nombre ou une chaîne selon le type de propriété
        """
        p=self.getProp(name)
        if isinstance(p,dbus.Array):
            if len(p)>0: return str(p[0])
            else: return ""
        elif isinstance(p,dbus.Boolean):
            return "%s" %bool(p)
        elif  isinstance(p,dbus.Int16) or isinstance(p,dbus.Int32) or isinstance(p,dbus.Int64) or isinstance(p,dbus.UInt16) or isinstance(p,dbus.UInt32) or isinstance(p,dbus.UInt64) or isinstance(p,int):
            return int(p)
        else:
            return "%s" %p

    def getFirstFat(self):
        """
        Renvoie la première partition VFAT
        @result la première partition VFAT ou None s'il n'y en a pas
        """
        if self.isDosFat(): return self
        return self.firstFat

    def ensureMounted(self):
        """
        Permet de s'assurer qu'une partition ou un disque sera bien monté
        @result le chemin du point de montage
        """
        mount_paths=self.getProp("device-mount-paths")
        if mount_paths==None: # le cas où la notion de montage est hors-sujet
            return ""
        leftTries=5
        while len(mount_paths)==0 and leftTries >0:
            leftTries = leftTries - 1
            path=self.getProp("device-file-by-path")
            if isinstance(path,dbus.Array) and len(path)>0:
                path=path[0]
                subprocess.call("udisks --mount %s > /dev/null" %path,shell=True)
                paths=self.getProp("device-mount-paths")
                if paths:
                    return self.getProp("device-mount-paths")[0]
                else:
                    time.sleep(0.5)
            else:
                time.sleep(0.5)
        if leftTries==0:
            raise Exception ("Could not mount the VFAT after 5 tries.")
        else:
            return mount_paths[0]

            
        
class Available:
    """
    une classe pour représenter la collection des disques USB connectés

    les attributs publics sont :
    - \b checkable booléen vrai si on veut gérer des sélections de disques
    - \b access le type d'accès qu'on veut pour les items
    - \b bus une instance de dbus.SystemBus
    - \b disks la collection de disques USB, organisée en un dictionnaire
       de disques : les clés sont les disques, qui renvoient à un ensemble
       de partitions du disque
    - \b enumdev une liste de chemins dbus vers les disques trouvés
    - \b firstFats une liste composée de la première partion DOS-FAT de chaque disque USB.
    """

    def __init__(self, checkable=False, access="disk", diskClass=uDisk, diskDict=None):
        """
        Le constructeur
        @param checkable : vrai si on veut pouvoir cocher les disques de la
          collection. Faux par défaut.
        @param access définit le type d'accès souhaité. Par défaut, c'est "disk"
          c'est à dire qu'on veut la liste des disques USB. Autres valeurs
          possibles : "firstFat" pour les premières partitions vfat.
        @param diskClass la classe de disques à créer
        @param diskDict un dictionnaire des disque maintenu par deviceListener
        """
        self.checkable=checkable
        self.access=access
        self.bus = dbus.SystemBus()
        proxy = self.bus.get_object("org.freedesktop.UDisks", 
                                    "/org/freedesktop/UDisks")
        iface = dbus.Interface(proxy, "org.freedesktop.UDisks")
        self.disks={}
        self.enumDev=iface.EnumerateDevices()
        ### récupération des disques usb dans le dictionnaire self.disks
        for path in self.enumDev:
            ud=diskClass(path, self.bus, checkable)
            if ud.isUsbDisk():
                self.disks[ud]=[]
                # cas des disques sans partitions
                if bool(ud.getProp("device-is-partition-table")) == False:
                    # la propriété "device-is-partition-table" est fausse,
                    # probablement qu'il y a un système de fichiers
                    self.disks[ud].append(ud)
        ### une deuxième passe pour récupérer et associer les partitions
        for path in self.enumDev:
            ud=diskClass(path, self.bus, checkable)
            for d in self.disks.keys():
                if ud.master() == d.path:
                    self.disks[d].append(ud)
        self.finishInit()

    def finishInit(self):
        """
        Fin de l'initialisation
        """
        self.mountFirstFats()

    def mountFirstFats(self):
        """
        fabrique la liste des partitions FAT,
        monte les partitions FAT si elles ne le sont pas
        """
        self.firstFats = self.getFirstFats()
        if self.access=="firstFat":
            for p in self.firstFats:
                p.ensureMounted()

    def __trunc__(self):
        """
        @return le nombre de medias connectés
        """
        return len(self.firstFats)

    def compare(self, other):
        """
        Sert à comparer deux collections de disques, par exemple
        une collection passée et une collection présente.
        @param other une instance de Available
        @return vrai si other semble être la même collection de disques USB
        """
        result=self.summary()==other.summary()
        return result

    def contains(self, ud):
        """
        Permet de déterminer si un disque est dans la collection
        @param ud une instance de uDisk
        @return vrai si le uDisk ud est dans la collection
        """
        for k in self.disks.keys():
            if k.getProp("device-file-by-path")==ud.getProp("device-file-by-path"): return True
        return False
    
    def summary(self):
        """
        Fournit une représentation imprimable d'un résumé
        @return une représentation imprimable d'un résumé de la collection
        """
        r=  "Available USB discs\n"
        r+= "===================\n"
        for d in sorted(self.disks.keys(), key=lambda disk: disk.getFatUuid()):
            r+="%s\n" %(d.title(),)
            if len(self.disks[d])>0:
                r+="    Partitions :\n"
                for part in sorted(self.disks[d], key=lambda disk: disk.getFatUuid()):
                    r+="        %s\n" %(part.path,)
        return r

    def __str__(self):
        """
        Fournit une représentation imprimable
        @return une représentation imprimable de la collection
        """
        r=  "Available USB discs\n"
        r+= "===================\n"
        for d in self.disks.keys():
            r+="%s\n" %d
            if len(self.disks[d])>0:
                r+="    Partitions :\n"
                for part in self.disks[d]:
                    r+="        %s\n" %(part.path)
                    r+=part.valuableProperties(12)+"\n"
        return r

    def __getitem__(self, n):
        """
        Renvoye le nième disque. Le fonctionnement dépend du paramètre
        self.access
        @param n un numéro
        @return le nième disque USB connecté
        """
        if self.access=="disk":
            return self.disks.keys()[n]
        elif self.access=="firstFat":
            return self.firstFats[n]

    def __len__(self):
        """
        Renseigne sur la longueur de la collection. Le fonctionnement
        dépend du paramètre self.access
        @return la longueur de la collection de disques renvoyée
        """
        if self.access=="disk":
            return len(self.disks)
        elif self.access=="firstFat":
            return len(self.firstFats)

    def getFirstFats(self, setOwners=False):
        """
        Facilite l'accès aux partitions de type DOS-FAT, et a des effets
        de bord :
          * marque le disque avec l'uuid de la première partition FAT.
          * construit une liste des chemins uDisk des FATs
        @param setOwners si égale à True,
          signale que la liste devra comporter des attributs de propriétaire
          de medias.
        @return une liste de partitions, constituée de la première
          partition de type FAT de chaque disque USB connecté
        """
        result=[]
        self.fatPaths=[]
        for d in self.disks.keys():
            for p in self.disks[d]:
                if p.isDosFat() or p==d :
                    # le cas p == d correspond aux disques non partitionnés
                    # on va supposer que dans ce cas la partition ne peut
                    # être que de type DOS !!!
                    result.append(p)
                    self.fatPaths.append(p.title())
                    # on marque le disque père et la partition elle-même
                    d.fatuuid=p.uuid
                    d.firstFat=p
                    p.fatuuid=p.uuid
                    if setOwners:
                        p.owner=d.owner
                    break
        return result

    def hasDev(self, dev):
        """
        @param dev un chemin comme /org/freedesktop/UDisks/devices/sdb3
        @return True si la partition est dans la liste des partions disponibles
        """
        s="%s" %dev
        s=s.replace("/org/freedesktop/UDisks/devices/","")
        for p in self.fatPaths:
            if p.split("/")[-1]==s:
                return True
        return False
    

if __name__=="__main__":
    machin=Available()
    print (machin)
    
