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
                logger.debug(QApplication.translate("uDisk","Disque occupé (Busy)",None, QApplication.UnicodeUTF8))
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
        self.logger.debug(QApplication.translate("uDisk","Détection des disques",None, QApplication.UnicodeUTF8))

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
        self.logger.debug(QApplication.translate("uDisk","Partition ajoutée %s",None, QApplication.UnicodeUTF8) % path)
        fstype = block.get_cached_property('IdType').get_string()
        self.logger.debug(QApplication.translate("uDisk","id-type %s ",None, QApplication.UnicodeUTF8) % fstype)

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
            # est-ce bien raisonnable de continuer avec un disque
            # qui n'est pas monté ???
            total = drive.get_cached_property('Size').get_uint64()
            free = -1
            mount = ''
        self.logger.debug('mount: %s' % mount)
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
            self.logger.debug(QApplication.translate("uDisk","On n'ajoute pas le disque : partition à 0 octets.",None, QApplication.UnicodeUTF8))            
             
    def _udisks_drive_added(self, obj, block, drive, path):
        if not drive:
            return
        self.logger.debug(QApplication.translate("uDisk","Disque ajouté : %s",None, QApplication.UnicodeUTF8) % path)
        
        size = drive.get_cached_property('Size').get_uint64()
        if size <= 0:
            self.logger.debug(QApplication.translate("uDisk","On n'ajoute pas le disque : partition à 0 octets.",None, QApplication.UnicodeUTF8))            
            return

        isUsb=False
        for s in block.get_cached_property('Symlinks'):
            if '/dev/disk/by-id/usb' in str(s):
                isUsb=True
        for s in block.get_cached_property('Symlinks'):
            if '/dev/disk/by-id/usb' in bytes(s).decode("utf-8"):
                isUsb=True
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
        self.logger.debug(QApplication.translate("uDisk","Changement pour le disque %s",None, QApplication.UnicodeUTF8) % path)
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
        self.fatuuid=None  # pour l'uuid de la première partion vfat
        self.firstFat=None # poignée de la première partition vfat
        # self.devStuff is the name of device which is usable to umount safely this object
        self.devStuff=self.ub.targets[self.path]["device"]

            
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
        
    def headers(locale="C"):
        """
        Méthode statique, pour avoir des titres de colonne.
        renvoie des titres pour les items obtenus par __getitem__. 
        @param locale la locale, pour traduire les titres éventuellement.
        Valeur par défaut : "C"
        @return une liste de titres de colonnes
        """
        result= list(uDisk._specialItems.keys())+ list(uDisk._itemNames.keys())
        return sorted(result)
        
    headers = staticmethod(headers)
    
    def devicePropProxy(self, bus):
        """
        renvoie un proxy vers un navigateur de propriétés
        @param bus une instace de dbus.SystemBus
        @return l'objet proxy
        """
        raise "obsoleteFunction"
        return self.device_prop

    def isTrue(self,prop, value=None):
        """
        Renvoie la valeur de vérité d'une propriété
        @param prop une propriété
        @param value
        @return vrai si la propriété est vraie (cas où value==None) ou vrai si la propriété a exactement la valeur value.
        """
        raise "obsoleteFunction"
        if value==None:
            return  bool(self.getProp(prop))
        else:
            return self.getProp(prop)==value
    
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
        raise "obsoleteFunction"

    def mountPoint(self):
        """
        Permet d'accèder à l'instance par un point de montage
        @return un point de montage, s'il en existe, sinon None
        """
        raise "obsoleteFunction"
   
    def getProp(self, name):
        """
        Facilite l'accès aux propriétés à l'aide des mots clés du module udisks
        @param name le nom d'une propriété
        @return une propriété dbus du disque ou de la partition, sinon None si le nom name est illégal
        """
        raise "obsoleteFunction"
        try:
            return self.device_prop.Get("org.freedesktop.UDisks", name)
        except:
            return None

    def isDosFat(self):
        """
        Permet de reconnaitre les partitions DOS-FAT
        @return True dans le cas d'une partition FAT16 ou FAT32
        """
        raise "obsoleteFunction"
        return self.getProp("id-type")=="vfat"

    def isMounted(self):
        """
        @return True si le disque ou la partion est montée
        """
        raise "obsoleteFunction"
        return bool(self.getProp("device-is-mounted"))
        
    def valuableProperties(self,indent=4):
        """
        Facilite l'accès aux propriétés intéressantes d'une instance
        @return une chaîne indentée avec les propriétés intéressantes, une par ligne
        """
        prefix="\n"+" "*indent
        r=""
        props=["mp", "isUsb", "parent", "fstype", "stickid", "uuid", "fatuuid", "vendor", "model", "devStuff"]
        for prop in props:
            r+=prefix+"%s = %s" %(prop, getattr(self,prop))
        return r

    def master(self):
        """
        renvoie le chemin du disque, dans le cas où self est une partition
        @return le chemin dbus du disque maître, sinon "/"
        """
        raise "obsoleteFunction"
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
        @return un élément si n>0, et le drapeau self.selected si n==0. 
        Les noms des éléments sont dans la liste itemNames utilisée dans 
        la fonction statique headers
        """
        propListe=self.headers()
        if n==0:
            return self.selected
        elif n <= len(propListe):
            return self.unNumberProp(n-1)

    def showableProp(self, name):
        """
        Renvoie une propriété dans un type "montrable" par QT.
        les propriétés que renvoie dbus ont des types inconnus de Qt4,
        cette fonction les transtype pour que QVariant arrive à les
        prendre en compte.
        @param name le nom de la propriété
        @return une nombre ou une chaîne selon le type de propriété
        """
        raise "obsoleteFunction"
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
        raise "obsoleteFunction"
        if self.isDosFat(): return self
        return self.firstFat

    def ensureMounted(self):
        """
        Permet de s'assurer qu'une partition ou un disque sera bien monté
        @result le chemin du point de montage
        """
        mount_paths=self.mp
        print ("GRRR self.mp =", mount_paths)
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

            
        
class Available:
    """
    une classe pour représenter la collection des disques USB connectés

    les attributs publics sont :
    - \b access le type d'accès qu'on veut pour les items
    - \b bus une instance de dbus.SystemBus
    - \b disks la collection de disques USB, organisée en un dictionnaire
       de disques : les clés sont les disques, qui renvoient à un ensemble
       de partitions du disque
    - \b enumdev une liste de chemins dbus vers les disques trouvés
    - \b firstFats une liste composée de la première partion DOS-FAT de chaque disque USB.
    """

    def __init__(self,access="disk", diskClass=uDisk2, diskDict=None):
        """
        Le constructeur
        @param access définit le type d'accès souhaité. Par défaut, c'est "disk"
          c'est à dire qu'on veut la liste des disques USB. Autres valeurs
          possibles : "firstFat" pour les premières partitions vfat.
        @param diskClass la classe de disques à créer
        @param diskDict un dictionnaire des disque maintenu par deviceListener
        """
        self.access=access
        self.ub = UDisksBackend()
        self.ub.detect_devices()
        self.disks={}
        self.enumDev=[dev for dev in self.ub.targets]
        ### récupération des disques usb dans le dictionnaire self.disks
        for path in self.enumDev:
            ud=diskClass(path, self.ub)
            if ud.isUsb:
                if not ud.parent:
                    self.disks[ud]=[]
                """
                # cas des disques sans partitions
                if bool(ud.getProp("device-is-partition-table")) == False:
                    # la propriété "device-is-partition-table" est fausse,
                    # probablement qu'il y a un système de fichiers
                    self.disks[ud].append(ud)
                """
        ### une deuxième passe pour récupérer et associer les partitions
        for path in self.enumDev:
            ud=diskClass(path, self.ub)
            for d in self.disks.keys():
                if ud.parent == d.path:
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
                if p.fstype=="vfat" or p==d :
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
"""
    # create logger
    logger = logging.getLogger("my_example")
    logger.setLevel(logging.DEBUG)
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    # logger.addHandler(ch)

    logger.addHandler(logging.NullHandler())

    ub=UDisksBackend(logger=logger)
    ub.detect_devices()
    print(ub.targets)
    
"""
