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


import dbus, subprocess, os, os.path, re, time, threading, logging
from dbus.mainloop.glib import DBusGMainLoop, threads_init
from gi.repository import Gio, GLib, UDisks
from PyQt4.QtGui import *

#################### activate debugging #######################
debug=False
def inspectData():
    return ""

if debug :
    logging.basicConfig(level=logging.DEBUG)
    import inspect
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

def abstract(func):
    """
    Cette "fabrique" permet de faire un décorateur @abstract.
    Le code est inspiré du projet USBcreator
    """
    def not_implemented(*args):
        raise NotImplementedError(QApplication.translate("uDisk","%s n'est pas implémenté actuellement",None, QApplication.UnicodeUTF8) %
                                  func.__name__)
    return not_implemented

def isCallable(obj):
    """
    Cette fonction utilise un ABC (abstract base class) pour dire si un
    objet possède ou non une méthode __call__
    @param obj un objet quelconque
    @return True si l'objet peut être utilisé comme fonction
    """
    import collections
    return isinstance(obj, collections.Callable)

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
    def __init__(self, allow_system_internal=False, bus=None, show_all=False, logger=logging):
        """
        Le constructeur.
        @param allow_system_internal à documenter
        @param bus un bus de dbus, si on ne précise rien ce sera
        dbus.SystemBus().
        @param show_all à documenter
        @param logger un objet permettant de journaliser les messages ; 
        par défaut il se confond avec le module logging
        """
        self.install_thread = None
        ## self.targets est un dictionnaire des disques détectés
        ## les clés sont les dsiques, et les contenus sont les partitions
        self.targets = {}
        self.cbHooks = []
        self.show_all = show_all
        self.allow_system_internal = allow_system_internal
        self.logger=logger
        self.logger.debug(QApplication.translate("uDisk","UDisksBackend : initialisation",None, QApplication.UnicodeUTF8))
        DBusGMainLoop(set_as_default=True)
        threads_init()
        if bus:
            self.bus = bus
        else:
            self.bus = dbus.SystemBus()

        self.udisks = UDisks.Client.new_sync(None)

    # voir le fichier integration-test issu des sources de udisks2
    def retry_mount(self, fs, timeout=3, retryDelay=0.3):
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
        Fait un inventaire des disques à prendre en compte. 
        Il faudra remonter les disques au programme graphique par des
        messages appropriés. L'ajout de disques n'est censé se faire
        qu'à leur mise en place durant le fonctionnement de la boucle
        principale.
        """
        self.logger.debug(QApplication.translate("uDisk","Détection des disques",None, QApplication.UnicodeUTF8)+inspectData())

        self.manager = self.udisks.get_object_manager()

        # mise en place des fonctions de rappel à utiliser pour tout changement
        self.cbHooks += [self.manager.connect('object-added', lambda man, obj: self._udisks_obj_added(obj))]
        self.cbHooks += [self.manager.connect('object-removed', lambda man, obj: self._device_removed(obj.get_object_path()))]
        self.cbHooks += [self.manager.connect('interface-added', lambda man, obj, iface: self._device_changed(obj))]
        self.cbHooks += [self.manager.connect('interface-removed', lambda man, obj, iface: self._device_changed(obj))]
        self.cbHooks += [self.manager.connect('interface-proxy-properties-changed', lambda man, obj, iface, props, invalid: self._device_changed(obj))]

        # recensement des disque actuellement connectés
        for obj in self.manager.get_objects():
            self._udisks_obj_added(obj)

    def target_removed_cb(self, drive):
        pass

    def target_added_cb(self, drive):
        pass

    def _udisks_obj_added(self, obj):
        """
        Fonction de rappel pour les ajouts de disque
        @param obj un objet renvoyé par l'évènement
        """
        # ne tient pas compte des périphériques non débranchables
        path = obj.get_object_path()
        for boring in not_interesting:
            if path.startswith(boring):
                return

        # ne considère que les périphériques de type block
        block = obj.get_block()
        if not block:
            return
        
        # initialise drive, nom du disque ?
        drive_name = block.get_cached_property('Drive').get_string()
        if drive_name != '/':
            drive = self.udisks.get_object(drive_name).get_drive()
        else:
            drive = None
        
        # on ne tient pas compte des CDROMS ni DVDROMS
        if drive and drive.get_cached_property('Optical').get_boolean():
            return

        # détermine si on a un disque ou une partition
        part = obj.get_partition()
        is_system = block.get_cached_property('HintSystem').get_boolean()
        if self.allow_system_internal or not is_system:
            if part:
                self._udisks_partition_added(obj, block, drive, path)
            else:
                self._udisks_drive_added(obj, block, drive, path)
            
    def _udisks_partition_added(self, obj, block, drive, path):
        self.logger.debug(QApplication.translate("uDisk","Partition ajoutée %s",None, QApplication.UnicodeUTF8) % path+inspectData())
        fstype = block.get_cached_property('IdType').get_string()
        self.logger.debug(QApplication.translate("uDisk","id-type %s ",None, QApplication.UnicodeUTF8) % fstype+inspectData())

        partition = obj.get_partition()
        parent = partition.get_cached_property('Table').get_string()
        fs = obj.get_filesystem()
        if fs:
            mount_points = fs.get_cached_property('MountPoints').get_bytestring_array()
            if fstype == 'vfat' and len(mount_points) == 0:
                try:
                    mount = self.retry_mount(fs)
                except:
                    logging.exception(QApplication.translate("uDisk","Échec au montage du disque : %s",None, QApplication.UnicodeUTF8) % path)
                    return
            else:
                mount = mount_points and mount_points[0]
        else:
            mount = None

        if mount:
            total, free = fs_size(mount)
        else:
            # si le disque n'est pas monté, on a accès à la taille mais pas
            # à son utilisation.
            total = drive.get_cached_property('Size').get_uint64()
            free = -1
            mount = ''
        self.logger.debug('mount: %s' % mount+inspectData())
        isUsb=False
        for s in block.get_cached_property('Symlinks'):
            if '/dev/disk/by-id/usb' in bytes(s).decode("utf-8"):
                isUsb=True
        if total > 1:
            self.targets[path] = {
                'isUsb'      : isUsb,
                'fstype'     : fstype,  
                'uuid'       : block.get_cached_property('IdUUID').get_string(),
                'serial'     : block.get_cached_property('Drive').get_string().split('_')[-1],
                'vendor'     : drive.get_cached_property('Vendor').get_string(),
                'model'      : drive.get_cached_property('Model').get_string(),
                'label'      : block.get_cached_property('IdLabel').get_string(),
                'free'       : free,
                'device'     : block.get_cached_property('Device').get_bytestring().decode('utf-8'),
                'capacity'   : total,
                'mountpoint' : mount,
                'parent'     : str(parent),
            }
            self._update_free(path)
            if self.show_all:
                if isCallable(self.target_added_cb):
                    self.target_added_cb(device)
            else:
                if parent in self.targets:
                    if isCallable(self.target_removed_cb):
                        self.target_removed_cb(parent)
                if isCallable(self.target_added_cb):
                    self.target_added_cb(path)
        else:
            self.logger.debug(QApplication.translate("uDisk","On n'ajoute pas le disque : partition à 0 octets.",None, QApplication.UnicodeUTF8)+inspectData())            
             
    def _udisks_drive_added(self, obj, block, drive, path):
        if not drive:
            return
        if path in self.targets:
            self.logger.debug(QApplication.translate("uDisk","Disque déjà ajouté auparavant : %s",None, QApplication.UnicodeUTF8) % path+inspectData())
        else:
            self.logger.debug(QApplication.translate("uDisk","Disque ajouté : %s",None, QApplication.UnicodeUTF8) % path+inspectData())
            
            size = drive.get_cached_property('Size').get_uint64()
            if size <= 0:
                self.logger.debug(QApplication.translate("uDisk","On n'ajoute pas le disque : partition à 0 octets.",None, QApplication.UnicodeUTF8)+inspectData())
                return
            isUsb=False
            for s in block.get_cached_property('Symlinks'):
                if '/dev/disk/by-id/usb' in bytes(s).decode("utf-8"):
                    isUsb=True
            if not isUsb:
                self.logger.debug(QApplication.translate("uDisk","On n'ajoute pas le disque : type non USB.",None, QApplication.UnicodeUTF8)+inspectData())
                return
            self.targets[path] = {
                'isUsb'      : isUsb,
                'fstype'     : '',  
                'uuid'       : block.get_cached_property('IdUUID').get_string(),
                'serial'     : block.get_cached_property('Drive').get_string().split('_')[-1],
                'vendor': drive.get_cached_property('Vendor').get_string(),
                'model' : drive.get_cached_property('Model').get_string(),
                'label' : '',
                'free'  : -1,
                'device': block.get_cached_property('Device').get_bytestring().decode('utf-8'),
                'capacity' : size,
                'mountpoint' : None,
                'parent' : None,
            }
            if isCallable(self.target_added_cb):
                if self.show_all:
                    self.target_added_cb(path)
                else:
                    children = [x for x in self.targets
                                if self.targets[x]['parent'] == path]
                    if not children:
                        self.target_added_cb(path)
            
    def _device_changed(self, obj):
        path = obj.get_object_path()
        self.logger.debug(QApplication.translate("uDisk","Changement pour le disque %s",None, QApplication.UnicodeUTF8) % path+inspectData())
        # As this will happen in the same event, the frontend wont change
        # (though it needs to make sure the list is sorted, otherwise it will).
        self._device_removed(path)
        self._udisks_obj_added(obj)

    def _device_removed(self, device):
        """
        Fonction de rappel déclenchée par le retrait d'un disque
        """
        logging.debug(QApplication.translate("uDisk","Disque débranché du système : %s",None, QApplication.UnicodeUTF8) % device)
        if device in self.targets:
            if isCallable(self.target_removed_cb):
                self.target_removed_cb(device)
            self.targets.pop(device)

    def update_free(self):
        """
        À documenter
        """
        for k in self.targets:
            changed = self._update_free(k)
            if changed and isCallable(self.target_changed_cb):
                self.target_changed_cb(k)
        return True

    # Internal functions.

    def _update_free(self, k):
        """
        À documenter
        """
        changed = False
        target = self.targets[k]
        free = target['free']
        target['free'] = fs_size(target['mountpoint'])[1]
        if free != target['free']:
            changed = True
        return changed

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

    def __init__(self, path, ub):
        """
        Le constructeur
        @param path un chemin comme '/org/freedesktop/UDisks2/block_devices/sdX'
        @param ub est une instance de UDisksBackend
        """
        self.path=path
        self.ub=ub
        self.selected=True
        self.rlock=threading.RLock()

        self.mp=self.ub.targets[self.path]["mountpoint"]
        self.isUsb=self.ub.targets[self.path]["isUsb"]
        self.vendor=self.ub.targets[self.path]["vendor"]
        self.model=self.ub.targets[self.path]["model"]
        self.parent=self.ub.targets[self.path]["parent"]
        self.fstype=self.ub.targets[self.path]["fstype"]
        self.stickid=self.ub.targets[self.path]["serial"]
        self.uuid=self.ub.targets[self.path]["uuid"]
        self.free=self.ub.targets[self.path]["free"]
        self.capacity=self.ub.targets[self.path]["capacity"]
        self.fatuuid=None  # pour l'uuid de la première partion vfat
        self.firstFat=None # poignée de la première partition vfat
        # self.devStuff is the name of device which is usable to umount safely this object
        self.devStuff=self.ub.targets[self.path]["device"]

            
    _itemNames={
        "1mp":QApplication.translate("uDisk","point de montage",None, QApplication.UnicodeUTF8),
        "2capacity":QApplication.translate("uDisk","taille",None, QApplication.UnicodeUTF8),
        "3vendor":QApplication.translate("uDisk","marque",None, QApplication.UnicodeUTF8),
        "4model":QApplication.translate("uDisk","modèle de disque",None, QApplication.UnicodeUTF8),
        "5stickid":QApplication.translate("uDisk","numéro de série",None, QApplication.UnicodeUTF8),
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
        props=["mp", "isUsb", "parent", "fstype", "stickid", "uuid", "fatuuid", "vendor", "model", "devStuff", "free", "capacity"]
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
        return [d for d in self.targets if self.targets[d]["parent"]==None]

    def parts(self, d):
        """
        Récolte les partitions d'un disque
        @param d le chemin vers un disque
        @return la liste des partitions de ce disque
        """
        return [p for p in self.targets if self.targets[p]["parent"]==d]

    def parts_ud(self, d):
        """
        Récolte les partitions d'un disque
        @param d le chemin vers un disque
        @return la liste des objets uDisk2 qui sont des partitions 
        de ce disque
        """
        return [uDisk2(p, self) for p in self.targets if self.targets[p]["parent"]==d]

    def summary(self):
        """
        Fournit une représentation imprimable d'un résumé
        @return une représentation imprimable d'un résumé de la collection
        """
        r=  "Available USB disks\n"
        r+= "===================\n"
        for d in sorted(self.disks()):
            r+="%s\n" %(self.targets[d]["device"])
            partlist=self.parts(d)
            if len(partlist)>0:
                r+="    Partitions :\n"
                for part in partlist:
                    r+="        %s\n" %(self.targets[part]["device"],)
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
                    r+="        %s\n" %(self.targets[part]["device"])
                    r+=uDisk2(part, self).valuableProperties(12)+"\n"
        return r

    def __getitem__(self, n):
        """
        Renvoye le nième disque. Le fonctionnement dépend du paramètre
        self.access
        @param n un numéro
        @return le nième disque USB connecté
        """
        if self.access=="disk":
            return uDisk2(self.targets.keys()[n], self)
        elif self.access=="firstFat":
            return uDisk2(self.firstFats[n],self)

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
        disks=[d for d in self.targets if self.targets[d]["parent"]==None]
        for d in disks:
            parts=[p for p in self.targets if self.targets[p]["parent"]==d]
            for p in parts:
                if self.targets[p]["fstype"]=="vfat":
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
        s="%s" %dev
        print(" !!!! IL FAUT DÉBOGUER ÇA CE CODE N'EST PAS PROPRE DANS hasDev")
        s=s.replace("/org/freedesktop/UDisks/devices/","")
        for p in self.fatPaths:
            if p.split("/")[-1]==s:
                return True
        return False
    

if __name__=="__main__":
    machin=Available()
    print (machin)
