# -*- coding: utf-8 -*-    
# 	$Id$	

licence={}
licence['en']="""
    file deviceListener.py
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
import dbus
from PyQt4.QtCore import *
import ownedUsbDisk

class DeviceListener:
    def __init__(self, widget=None):
        """
        le constructeur
        @param widget un QWidget qui s'intéresse aux disques amovibles
        """
        self.bus = dbus.SystemBus()
        self.manager = self.bus.get_object(
            'org.freedesktop.UDisks',
            '/org/freedesktop/UDisks')
        self.interface = dbus.Interface(
            self.manager,
            'org.freedesktop.UDisks')
        self.interface.connect_to_signal('DeviceAdded', self.cbAdd)
        self.interface.connect_to_signal('DeviceChanged', self.cbChange)
        self.interface.connect_to_signal("DeviceRemoved",self.cbDel)
        self.connectedVolumes={}
        self.widget=widget
        self.pollDevices()

    def pollDevices(self):
        """
        peuple le dictionnaire self.connectedVolumes avec les volumes
        actuellement gérés par dbus.
        """
        self.connectedVolumes={}
        for d in self.interface.EnumerateDevices():
            pathUDisks=self.vfatUsbPath(d)
            if pathUDisks:
                self.connectedVolumes[pathUDisks]=d
        return
    
    def cbAdd(self, path):
        """
        fonction de rappel pour une clé qu'on vient de brancher
        @param path un chemin de type UDisks vers une partition
        """
        key=self.vfatUsbPath(path)
        if key:
            self.connectedVolumes[key]=path
            if self.widget:
                self.widget.emit(SIGNAL("deviceAdded(QString)"), key)
        return

    def cbChange(self, path):
        """
        fonction de rappel pour une clé qui vient de changer de type
        @param path un chemin de type UDisks vers une partition
        """
        key=self.vfatUsbPath(path)
        if key and not key in self.connectedVolumes:
            self.connectedVolumes[key]=path
            if self.widget:
                self.widget.emit(SIGNAL("deviceAdded(QString)"), key)
        return

           
    def cbDel(self, path):
        """
        fonction de rappel pour une clé retirée
        @param path un chemin de type UDisks vers une partition
        """
        key=str(path)
        if key in self.connectedVolumes:
            if self.widget:
                self.widget.emit(SIGNAL("deviceRemoved(QString)"), key)
                self.connectedVolumes.pop(key)
        return

    def vfatUsbPath(self, dev):
        """
        Détermine le chemin UDisks pour une partition vfat connectée par USB
        @param dev est un objet dbus renvoyé par EnumerateDevices(), ou une
        simple chaine de caractères, clé dans le tableau connectedVolumes
        @return un chemin vers le disque (selon UDisks), sinon ""
        """
        if type(dev)==type(""):
            dev=self.connectedVolumes[dev]
        o=self.bus.get_object("org.freedesktop.UDisks", dev)
        if self.isVfatUsb(o):
            return str(dev)
        return ""

    def identify(self,dev):
        """
        Renvoie une identification de baladeur pour scolasync
        @param dev est un objet dbus renvoyé par EnumerateDevices(), ou une
        simple chaine de caractères, clé dans le tableau connectedVolumes
        @return un triplet (stickId, tatouage, uuid)
        """
        if type(dev)==type(""):
            dev=self.connectedVolumes[dev]
        o=self.bus.get_object("org.freedesktop.UDisks", dev)
        i=dbus.Interface(o, "org.freedesktop.DBus.Properties")
        stickId, tattoo, uuid = "", "", ""
        try:
            p=i.Get('','DeviceMountPaths')
            if len(p) > 0:
                mountPoint=str(p[0])
                tattoo=ownedUsbDisk.tattooInDir(mountPoint)
        except:
            pass
        try:
            uuid=str(i.Get('','IdUuid'))
        except:
            pass
        try:
            stickId=str(i.Get("", "DriveSerial"))
        except:
            pass
        return (stickId, tattoo, uuid)


    def isVfatUsb(self, o):
        """
        Décide si une partition est de type vfat, et connectée par USB
        @param o un objet dbus correspondant à une partition
        """
        i=dbus.Interface(o, "org.freedesktop.DBus.Properties")
        try:
            result=str(i.Get('','DriveConnectionInterface'))=="usb" and \
                   str(i.Get('','IdType'))=="vfat"
        except:
            result=False
        return result
 
