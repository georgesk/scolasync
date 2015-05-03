# -*- coding: utf-8 -*-    
# $Id: usbDisk2.py 36 2014-03-16 19:37:27Z georgesk $	

licence={}
licence_en="""
    file usbDisk2.py
    this file is part of the project scolasync. It is a rewrite of
    usbDisk.py to take in account udisks2.
    
    Copyright (C) 2014 Georges Khaznadar <georgesk@ofset.org>

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


import dbus, subprocess, os, os.path, re, time, threading, logging, inspect
from dbus.mainloop.glib import DBusGMainLoop, threads_init
from gi.repository import Gio, GLib, UDisks
from PyQt4.QtGui import *

#################### activate debugging #######################
debug=False
def inspectData():
    return ""

if debug :
    logging.basicConfig(level=logging.DEBUG)
    def inspectData():
        caller=1
        callerframerecord = inspect.stack()[caller]
        frame = callerframerecord[0]
        info = inspect.getframeinfo(frame)
        return " -- file={0}, function={1}, line={2}".format(
            info.filename, info.function, info.lineno
            )
else:
    pass
    # logging.basicConfig(level=logging.NOTSET)
###############################################################

def fs_size(device):
    """
    Renvoie la taille d'un système de fichier et la place disponible
    @return un tuple : taille totale et espace libre
    """
    try:
        stat = os.statvfs(device)
    except:
        return (0, 0)
    free = stat.f_bsize * stat.f_bavail # les blocs réservés sont inclus
    total = stat.f_bsize * stat.f_blocks
    return (total, free)


############ la variable suivante a été recopiées à l'aveugle ################
############ depuis un fichier du projet USBcreator ##########################
no_options = GLib.Variant('a{sv}', {})
##############################################################################
##############################################################################

######### des "chemins" correspondant à des disques non débranchables ########
not_interesting = (
    # boucle
    '/org/freedesktop/UDisks2/block_devices/loop',
    # disque raid
    '/org/freedesktop/UDisks2/block_devices/dm_',
    # mémoire vive
    '/org/freedesktop/UDisks2/block_devices/ram',    
    '/org/freedesktop/UDisks2/block_devices/zram',
    # disques durs
    '/org/freedesktop/UDisks2/drives/', 
    )

class UDisksBackend:
    """
    Cette classe a été inspirée par le projet USBcreator. 
    Plusieurs modifications ont été faites au code original.
    Les fonctions de rappel ne tiennent compte que des périphériques USB
    """
    def __init__(self, logger=logging):
        """
        Le constructeur.
        @param logger un objet permettant de journaliser les messages ; 
        par défaut il se confond avec le module logging
        """
        self.install_thread = None
        self.logger=logger
        ## self.targets est un dictionnaire des disques détectés
        ## les clés sont les paths et les contenus des instances de uDisk2
        self.targets = {}
        ## self.modified signifie une modification récente, à prendre en compte
        ## par une application au niveau utilisateur
        self.modified=False
        DBusGMainLoop(set_as_default=True)
        threads_init()
        self.bus = dbus.SystemBus()
        self.udisks = UDisks.Client.new_sync(None)
        self.manager = self.udisks.get_object_manager()
        self.cbHooks = {
            'object-added':      {
                'profile': ['man', 'obj'],
                'hooks'  : []
                },
            'object-removed':      {
                'profile': ['man', 'obj'],
                'hooks'  : []
                },
            'interface-added':      {
                'profile': ['man', 'obj'],
                'hooks'  : []
                },
            'interface-removed':      {
                'profile': ['man', 'obj'],
                'hooks'  : []
                },
            'interface-proxy-properties-changed':      {
                'profile': ['man', 'obj', 'interface'],
                'hooks'  : []
                },
        }
        # mise en place des fonctions de rappel à utiliser pour tout changement
        self.addHook('object-added',
                     lambda man, obj: self._udisks_obj_added(obj))
        self.addHook('object-removed',
                     lambda man, obj: self._udisks_obj_removed(obj))
        self.addHook('interface-added',
                     lambda man, obj, iface: self._device_changed(obj))
        self.addHook('interface-removed',
                     lambda man, obj, iface: self._device_changed(obj))
        self.addHook('interface-proxy-properties-changed',
                     lambda man, obj, iface, props, invalid: self._device_changed(obj))

    def addHook(self, signal, func):
        """
        ajoute une fonction à appeler pour un signal nommé, et enregistre
        cette fonction dans self.cbHooks, après vérification de sa liste
        de paramètres.
        @param signal une chaîne
        @param func une fonction
        @return le résultat de l'appel à self.manager.connect(signal,func)
        """
        if inspect.getargspec(func).args == self.cbHooks[signal]['profile']:
            cb=self.manager.connect(signal,func)
            self.cbHooks[signal]['hooks'].append(cb)
            return cb
        return None
    
    # voir le fichier integration-test issu des sources de udisks2
    def retry_mount(self, fs, timeout=5, retryDelay=0.3):
        """
        Essaie de monter un système de fichier jusqu'à ce qu'il
        cesse d'échouer avec "Busy". Échoue si l'erreur est autre
        que "Busy".
        @param fs un système de fichier à monter
        @param timeout nombre de secondes d'attente au maximum
        @param retryDelay délai entre deux essais
        """
        while timeout >= 0:
            try:
                return fs.call_mount_sync(no_options, None)
            except GLib.GError as e:
                if not 'UDisks2.Error.DeviceBusy' in e.message:
                    raise
                logger.debug(QApplication.translate("uDisk","Disque occupé (Busy)",None, QApplication.UnicodeUTF8)+inspectData())
                time.sleep(retryDelay)
                timeout -= retryDelay
        return ''

    def detect_devices(self):
        """
        Fait un inventaire des disques. 
        """
        for obj in self.manager.get_objects():
            self._udisks_obj_added(obj)

    def _interesting_obj(self, obj):
        """
        trouve si un objet est intéressant à cataloguer
        @param obj une instance de UDisksObjectProxy
        @return un triplet interesting (vrai/faux), drive (objet),
        partition (objet).
        """
        interesting=False
        drive=None
        partition=None
        
        # ne tient pas compte des périphériques non débranchables
        path = obj.get_object_path()
        for boring in not_interesting:
            if path.startswith(boring):
                return interesting, drive, partition

        # ne considère que les périphériques de type block
        block = obj.get_block()
        if not block:
            return interesting, drive, partition
        
        # initialise drive, nom du disque ?
        drive_name = block.get_cached_property('Drive').get_string()
        if drive_name == '/':
            return interesting, drive, partition
        else:
            drive = self.udisks.get_object(drive_name).get_drive()
        
        # on ne tient pas compte des CDROMS ni DVDROMS
        if drive and drive.get_cached_property('Optical').get_boolean():
            return interesting, drive, partition

        interesting=True
        # détermine si on a un disque ou une partition
        partition = obj.get_partition()
        return interesting, drive, partition
    
    def _udisks_obj_added(self, obj):
        """
        Fonction de rappel pour les ajouts de disque
        @param obj un objet renvoyé par l'évènement
        """
        interesting, drive, part = self._interesting_obj(obj)
        if part:
            self._udisks_partition_added(obj, drive, part)
        elif drive:
            self._udisks_drive_added    (obj, drive, part)
        return

    def objIsUsb(self,obj):
        """
        détermine si un périphérique est de type USB
        @param obj un objet UDisksObjectProxy
        @return vrai si c'est un périphérique USB
        """
        for s in obj.get_block().get_cached_property('Symlinks'):
            if b'/dev/disk/by-id/usb' in bytes(s):
                return True
        return False
    
    def _udisks_partition_added(self, obj, drive, partition):
        """
        Fonction de rappel pour l'ajout d'une partition,
        met à jour self.targets
        @param obj une instance de UDisksObjectProxy
        @param drive une instance de ...
        @param partition une instance de ...
        """
        path  = obj.get_object_path()
        block = obj.get_block()
        self.logger.debug(QApplication.translate("uDisk","Partition ajoutée %s",None, QApplication.UnicodeUTF8) % path+inspectData())
        fstype = block.get_cached_property('IdType').get_string()
        parent = partition.get_cached_property('Table').get_string()
        total = drive.get_cached_property('Size').get_uint64()
        free = -1
        mount = ''
        fs = obj.get_filesystem()
        if fs:
            mount_points = fs.get_cached_property('MountPoints').get_bytestring_array()
            if len(mount_points)>0:
                mount= mount_points[0]
            if not mount and fstype == 'vfat':
                try:
                    mount = self.retry_mount(fs)
                except:
                    logging.exception(QApplication.translate("uDisk","Échec au montage du disque : %s",None, QApplication.UnicodeUTF8) % path)
        if mount:
            total, free = fs_size(mount)
        isUsb=self.objIsUsb(obj)
        if not isUsb:
            self.logger.debug(QApplication.translate("uDisk","On n'ajoute pas le disque : partition non-USB",None, QApplication.UnicodeUTF8)+inspectData())
        elif total < 1:
            self.logger.debug(QApplication.translate("uDisk","On n'ajoute pas le disque : partition vide",None, QApplication.UnicodeUTF8)+inspectData())
        else:
            udisk=uDisk2(
                path=path, mp=mount, isUsb=isUsb,
                vendor=drive.get_cached_property('Vendor').get_string(),
                model=drive.get_cached_property('Model').get_string(),
                parent=str(parent),
                fstype=fstype,
                serial=block.get_cached_property('Drive').get_string().split('_')[-1],
                uuid=block.get_cached_property('IdUUID').get_string(),
                free=free,
                capacity=total,
                device=block.get_cached_property('Device').get_bytestring().decode('utf-8'),
            )
            self.targets[path] = udisk
            self.modified=True
        return
             
    def _udisks_drive_added(self, obj, drive, part):
        path  = obj.get_object_path()
        block = obj.get_block()
        if path in self.targets:
            self.logger.debug(QApplication.translate("uDisk","Disque déjà ajouté auparavant : %s",None, QApplication.UnicodeUTF8) % path+inspectData())
            return
        self.logger.debug(QApplication.translate("uDisk","Disque ajouté : %s",None, QApplication.UnicodeUTF8) % path+inspectData())
        size = drive.get_cached_property('Size').get_uint64()
        ##### désactivé, quelquefois drive.get_cached_property('Size').get_uint64()
        ##### renvoie des résultats erronés juste après le branchement
        """
        if size <= 0:
            self.logger.debug(QApplication.translate("uDisk","On n'ajoute pas le disque : partition à 0 octets.",None, QApplication.UnicodeUTF8)+inspectData())
            return
        """
        isUsb = self.objIsUsb(obj)
        if not isUsb:
            self.logger.debug(QApplication.translate("uDisk","On n'ajoute pas le disque : partition non-USB",None, QApplication.UnicodeUTF8)+inspectData())
        else:
            udisk=uDisk2(
                path=path,
                isUsb=isUsb,
                parent='',
                vendor=drive.get_cached_property('Vendor').get_string(),
                model=drive.get_cached_property('Model').get_string(),
                serial=block.get_cached_property('Drive').get_string().split('_')[-1],
                uuid=block.get_cached_property('IdUUID').get_string(),
                capacity=size,
                device=block.get_cached_property('Device').get_bytestring().decode('utf-8'),
            )
            self.targets[path] =udisk
            self.modified=True
        return
        
    def _device_changed(self, obj):
        path = obj.get_object_path()
        self.logger.debug(QApplication.translate("uDisk","Changement pour le disque %s",None, QApplication.UnicodeUTF8) % path+inspectData())

    def _udisks_obj_removed(self, obj):
        """
        Fonction de rappel déclenchée par le retrait d'un disque.
        Met à jour self.targets
        @param obj une instance de UDisksObjectProxy
        """
        path=obj.get_object_path()
        logging.debug(QApplication.translate("uDisk","Disque débranché du système : %s",None, QApplication.UnicodeUTF8) % path)
        if path in self.targets:
            self.targets.pop(path)
            self.modified=True


class uDisk2:
    """
    une classe pour représenter un disque ou une partition.

    les attributs publics sont :
    - \b path  le chemin dans le système dbus
    - \b device l'objet dbus qui correspond à l'instance
    - \b device_prop un proxy pour questionner cet objet dbus
    - \b selected booléen vrai si on doit considérer cette instance comme sélectionnée. Vrai à l'initialisation
    - \b rlock un verrou récursif permettant de réserver l'usage du media pour un seul thread
    """

    def __init__(self, path, mp='', isUsb=False, vendor='', model='', parent=None,
                 fstype='', serial='', uuid='',
                 free=0, capacity=0, device='', firstFat=False, selected=True):
        """
        Le constructeur
        @param path un chemin comme '/org/freedesktop/UDisks2/block_devices/sdX'
        @param mp point de montage ('' par défaut)
        @param isUsb en général, vrai vu qu'on se s'intéressera qu'à des périphériques
        USB
        @param vendor indication de vendeur
        @param model indication de modèle
        @param parent périphérique parent (None par défaut)
        @param fstype type de système de fichiers
        @param serial numéro de série
        @param uuid identifiant donné au disque lors du formatage
        @param free taille de la zone libre pour l'écriture
        @param capacity taille du périphérique
        @param device pseudo-fichier pour l'accès au périphérique
        @param firstFat vrai s'il s'agit de la première partition de type vfat
        @param selected vrai/faux selon qu'on sélectionne ou non le périphérique (vrai par défaut)
        """
        self.path=path
        self.mp=mp
        self.isUsb=isUsb
        self.vendor=vendor
        self.model=model
        self.parent=parent
        self.fstype=fstype
        self.stickid=serial
        self.uuid=uuid
        self.free=free
        self.capacity=capacity
        self.devStuff=device
        self.firstFat=firstFat
        self.selected=selected
        self.rlock=threading.RLock()
        return
            
    _itemNames={
        "1mp":QApplication.translate("uDisk","point de montage",None, QApplication.UnicodeUTF8),
        "2capacity":QApplication.translate("uDisk","taille",None, QApplication.UnicodeUTF8),
        "3vendor":QApplication.translate("uDisk","marque",None, QApplication.UnicodeUTF8),
        "4model":QApplication.translate("uDisk","modèle de disque",None, QApplication.UnicodeUTF8),
        "5stickid":QApplication.translate("uDisk","numéro de série",None, QApplication.UnicodeUTF8),
        }

    _specialItems={"0Check":QApplication.translate("uDisk","cocher",None, QApplication.UnicodeUTF8)}

    _ItemPattern=re.compile("[0-9]?(.*)")
    
    def uniqueId(self):
        """
        renvoie un identifiant unique. Dans cette classe, cette fonction
        est synonyme de file()
        @return un identifiant unique, garanti par le système de fichiers
        """
        return self.file()
        
    def headers(locale="C"):
        """
        Méthode statique, pour avoir des titres de colonne.
        renvoie des titres pour les items obtenus par __getitem__. 
        @param locale la locale, pour traduire les titres éventuellement.
        Valeur par défaut : "C"
        @return une liste de titres de colonnes
        """
        result= list(uDisk2._specialItems.keys())+ list(uDisk2._itemNames.keys())
        return sorted(result)
        
    headers = staticmethod(headers)
    
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

    def isDosFat(self):
        """
        Permet de reconnaitre les partitions DOS-FAT
        @return True dans le cas d'une partition FAT16 ou FAT32
        """
        return self.fstype=="vfat"

    def isMounted(self):
        """
        @return True si le disque ou la partion est montée
        """
        return bool(self.mp)
        
    def valuableProperties(self,indent=4):
        """
        Facilite l'accès aux propriétés intéressantes d'une instance
        @return une chaîne indentée avec les propriétés intéressantes, une par ligne
        """
        prefix="\n"+" "*indent
        r=""
        props=["mp", "isUsb", "parent", "fstype", "stickid", "uuid", "vendor", "model", "devStuff", "free", "capacity"]
        for prop in props:
            r+=prefix+"%s = %s" %(prop, getattr(self,prop))
        return r

    def mountPoint(self):
        """
        @return le point de montage
        """
        return self.mp

    def unNumberProp(self,n):
        """
        retire le numéro des en-têtes pour en faire un nom de propriété
        valide pour interroger dbus
        @param n un numéro de propriété qui se réfère aux headers
        @return une propriété renvoyée par dbus, dans un format imprimable
        """
        m=uDisk2._ItemPattern.match(self.headers()[n])
        try:
            return getattr(self, m.group(1))
        except:
            return ""
        
    def __getitem__(self,n):
        """
        Renvoie un élément de listage de données internes au disque
        @param n un nombre
        @return un élément si n>0, et le drapeau self.selected si n==0. 
        Les noms des éléments sont dans la liste itemNames utilisée dans 
        la fonction statique headers
        """
        propListe=self.headers()
        if n==0:
            return self.selected
        elif n <= len(propListe):
            return self.unNumberProp(n-1)

    def ensureMounted(self):
        """
        Permet de s'assurer qu'une partition ou un disque sera bien monté
        @result le chemin du point de montage
        """
        mount_paths=self.mp
        if mount_paths==None: # le cas où la notion de montage est hors-sujet
            return ""
        leftTries=5
        while len(mount_paths)==0 and leftTries >0:
            leftTries = leftTries - 1
            path=self.path
            if len(path)>0:
                subprocess.call("udisks --mount %s > /dev/null" %path,shell=True)
                paths=self.mp
                print("STILL TO DEBUG: is the mount OK? is self.mp updated?")
                if paths:
                    return paths
                else:
                    time.sleep(0.5)
            else:
                time.sleep(0.5)
        if leftTries==0:
            raise Exception ("Could not mount the VFAT after 5 tries.")
        else:
            return mount_paths

            
        
class Available (UDisksBackend):
    """
    une classe pour représenter la collection des disques USB connectés

    les attributs publics sont :
    - \b access le type d'accès qu'on veut pour les items
    - \b targets la collection de disques USB, organisée en un dictionnaire
       de disques : les clés sont les disques, qui renvoient à un ensemble
       de partitions du disque
    - \b firstFats une liste composée de la première partion DOS-FAT de chaque disque USB.
    """

    def __init__(self, access="disk", diskClass=uDisk2):
        """
        Le constructeur
        @param access définit le type d'accès souhaité. Par défaut, c'est "disk"
          c'est à dire qu'on veut la liste des disques USB. Autres valeurs
          possibles : "firstFat" pour les premières partitions vfat.
        @param diskClass la classe de disques à créer
        """
        UDisksBackend.__init__(self)
        self.access=access
        self.detect_devices()
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
                uDisk2(p,self).ensureMounted()

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
        return ud.path in self.targets
    
    def disks(self):
        """
        Récolte les enregistrements de niveau supérieur de self.targets
        @return la liste des chemins vers les disque USB détectés
        """
        return [d for d in self.targets if not self.targets[d].parent]

    def parts(self, d):
        """
        Récolte les partitions d'un disque
        @param d le chemin vers un disque
        @return la liste des partitions de ce disque
        """
        return [p for p in self.targets if self.targets[p].parent==d]

    def parts_ud(self, d):
        """
        Récolte les partitions d'un disque
        @param d le chemin vers un disque
        @return la liste des objets uDisk2 qui sont des partitions 
        de ce disque
        """
        return [self.targets[p] for p in self.targets if self.targets[p].parent==d]

    def summary(self):
        """
        Fournit une représentation imprimable d'un résumé
        @return une représentation imprimable d'un résumé de la collection
        """
        r=  "Available USB disks\n"
        r+= "===================\n"
        for d in sorted(self.disks()):
            r+="%s\n" %(self.targets[d].devStuff)
            partlist=self.parts(d)
            if len(partlist)>0:
                r+="    Partitions :\n"
                for part in partlist:
                    r+="        %s\n" %(self.targets[part].devStuff,)
        return r

    def __str__(self):
        """
        Fournit une représentation imprimable
        @return une représentation imprimable de la collection
        """
        r=  "Available USB disks\n"
        r+= "===================\n"
        for d in self.disks():
            r+="%s\n" %d
            partlist=self.parts(d)
            if len(partlist)>0:
                r+="    Partitions :\n"
                for part in sorted(partlist):
                    r+="        %s\n" %(self.targets[part].devStuff)
                    r+=self.targets[part].valuableProperties(12)+"\n"
        return r

    def __getitem__(self, n):
        """
        Renvoye le nième disque. Le fonctionnement dépend du paramètre
        self.access
        @param n un numéro
        @return le nième disque USB connecté
        """
        if self.access=="disk":
            return self.targets.keys()[n]
        elif self.access=="firstFat":
            return self.firstFats[n]

    def __len__(self):
        """
        Renseigne sur la longueur de la collection. Le fonctionnement
        dépend du paramètre self.access
        @return la longueur de la collection de disques renvoyée
        """
        if self.access=="disk":
            return len(self.targets)
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
        disks=[d for d in self.targets if not self.targets[d].parent]
        for d in disks:
            parts=[p for p in self.targets if self.targets[p].parent==d]
            for p in parts:
                if self.targets[p].fstype=="vfat":
                    result.append(p)
                    self.fatPaths.append(p)
                    if setOwners:
                        print(" !!!! IL FAUT DÉBOGUER ÇA CE CODE N'EST PAS PROPRE DANS getFirstFats")
                        p.owner=d.owner
                    break
        return result

    def hasDev(self, dev):
        """
        @param dev un chemin comme /org/freedesktop/UDisks/devices/sdb3
        @return True si la partition est dans la liste des partions disponibles
        """
        s=str(dev)
        for p in self.fatPaths:
            if p.split("/")[-1]==s:
                return True
        return False
    

if __name__=="__main__":
    from PyQt4.QtCore import *
    from PyQt4.QtGui import *
    import sys
    class MainWindow(QMainWindow):
        def __init__(self):
            QMainWindow.__init__(self)

            # The only thing in the app is a quit button
            quitbutton = QPushButton('Close', self)
            self.setCentralWidget(quitbutton)
    

    machin=Available()
    print (machin)
    def print_targets_if_modif(man, obj):
        if machin.modified:
            print([s.split("/")[-1] for s in machin.targets.keys()])
        machin.modified=False
    machin.addHook('object-added',   print_targets_if_modif)
    machin.addHook('object-removed', print_targets_if_modif)
        
    app = QApplication(sys.argv)
    main = MainWindow()
    main.show()
    sys.exit(app.exec_())
