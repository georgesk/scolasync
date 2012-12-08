#!/usr/bin/python
# -*- coding: utf-8 -*-
# 	$Id: help.py 47 2011-06-13 10:20:14Z georgesk $	

licence={}
licence['en']="""
    file help.py
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
import version
from globaldef import _dir
from xml.dom.minidom import parse

class helpWindow(QDialog):
    def __init__(self, parent=None):
        """
        Le constructeur
        """
        QDialog.__init__(self, parent)
        from Ui_help import Ui_Aide
        self.ui=Ui_Aide()
        self.ui.setupUi(self)
        self.ui.labelVersion.setText(QApplication.translate("Main","Version numéro {major}.{minor}",None, QApplication.UnicodeUTF8).format(major=version.major(), minor=version.minor()))
        self.loadBrowsers(_dir("help"),self.parent().locale)
        QObject.connect(self.ui.closeButton, SIGNAL("clicked()"), self.close)

    def loadBrowsers(self, dir, locale):
        """
        met en place les textes dans les afficheurs, en fonction de la locale.
        le répertoire où sont les textes au format HTML est \b dir.
        @param dir le répertoire où sont les fichiers HTML
        @param locale la langue choisie
        """
        self.ui.usageBrowser.setHtml(QUrl("file://"+dir+"/usage_"+locale+".html"))
        self.ui.authorsBrowser.setHtml(QUrl("file://"+dir+"/authors_"+locale+".html"))
        self.ui.licenseBrowser.setHtml(QUrl("file://"+dir+"/license_"+locale+".html"))
        self.ui.languagesBrowser.setHtml(QUrl("file://"+dir+"/languages_"+locale+".html"))
        # parses the manual-tab's text to include the custom
        # manual's URL.
        manuals=parse(dir+"/manual_"+locale+".html")
        dl=manuals.documentElement.getElementsByTagName("dl")[0]
        dd=dl.getElementsByTagName("dd")[1]
        a=dd.getElementsByTagName("a")[0]
        a.setAttribute("href", self.parent().manFileLocation)
        # then sets the manual-tab's contents
        self.ui.manualBrowser.setText(manuals.toxml())
