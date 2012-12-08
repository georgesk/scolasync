#!/usr/bin/python
# -*- coding: utf-8 -*-
# 	$Id: mytextbrowser.py 8 2010-10-11 10:03:05Z georgesk $	

licence={}
licence['en']="""
    file mytextbrowser.py
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
import subprocess

class myTextBrowser(QTextBrowser):
    """
    Une classe qui ouvre Firefox quand on clique sur un lien externe
    """
    def setSource(self,url):
        """
        lance Firefox en tâche de fond.
        @param url l'adresse à ouvrir.
        """
        subprocess.call("(firefox %s &)"%url.toString(),shell=True)
        
    def setHtml(self,url):
        """
        lien vers la méthode setSource originale
        @param url l'adresse à ouvrir.
        """
        QTextBrowser.setSource(self,QUrl(url))
