#!/usr/bin/python
# -*- coding: utf-8 -*-
# 	$Id: notification.py 29 2010-12-11 15:39:59Z georgesk $	

licence={}
licence['en']="""
    file notification.py
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
 

class Notification:
    """
    Une classe pour afficher des notifications à l'écran. Doit
    fonctionner avec tous les gestionnaires de bureau qui adhèrent aux
    standards de freedesktop.org.
    Cette classe est basée sur la documentation disponible à
    http://www.galago-project.org/specs/notification/0.9/x408.html
    """
 
    def __init__(self, app_name ="", replaces_id=0, app_icon="",
                     summary="", body="", actions=[], hints={},
                     expire_timeout=1000):
            """
            Le constructeur
            @param app_name nom d'une application, valeur par défaut =""
            @param replaces_id identifiant d'une notification à remplacer valeur par défaut=0
            @param app_icon nom d'un fichier servant pour l'icône valeur par défaut=""
            @param summary description brève de la notification valeur par défaut =""
            @param body le texte de la notification, valeur pa défaut=""
            @param actions une liste de paires représeantant des actions, valeur par défaut=[]
            @param hints un dictionnaire de suggestions, valeur par défaut={},
            @param expire_timeout durée maximale d'affichage en millisecondes, valeur par défaut=1000
            """
            self.app_name = app_name
            self.replaces_id = replaces_id
            self.app_icon = app_icon
            self.summary = summary
            self.body = body
            self.actions = actions
            self.hints = hints
            self.expire_timeout = expire_timeout
            
            try:
                session_bus = dbus.SessionBus()
                obj = session_bus.get_object("org.freedesktop.Notifications","/org/freedesktop/Notifications")
                self.interface = dbus.Interface(obj, "org.freedesktop.Notifications")
            except Exception:
                self.interface = None
 
    def notify(self):
        self.interface.Notify(self.app_name, self.replaces_id, self.app_icon, self.summary, self.body, self.actions, self.hints, self.expire_timeout)
            
            
if __name__=="__main__":
    notif = Notification(app_name="AppliTest",
                         summary="Notification de test",
                         body="Voici le corps de la notification",
                         app_icon="/usr/share/pixmaps/vlc.png",
                         expire_timeout=7000)
    notif.notify()
