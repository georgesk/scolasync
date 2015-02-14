#!/usr/bin/python
# -*- coding: utf-8 -*-
# 	$Id: diskFull.py 33 2010-12-12 00:39:46Z georgesk $	

licence={}
licence['en']="""
    file diskFull.py
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

from PyQt4.QtCore import *
from PyQt4.QtGui import *

class mainWindow(QMainWindow):
    def __init__(self, parent, percent, total=0, used=0, title="Disk"):
        """
        Le constructeur
        @param parent un QWidget
        @param percent un pourcentage de remplissage de disque
        @param total place totale en kilo-octets
        @param used place utilisée en kilo-octets
        @param title le titre pour la fenêtre
        """
        QMainWindow.__init__(self)
        QWidget.__init__(self, parent)
        from Ui_diskFull  import Ui_MainWindow
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle(title)
        self.v=self.ui.graphicsView
        self.total=self.ui.label_total
        self.used=self.ui.label_used
        self.v.setScene(sceneWithUsage(self.v, QRectF(5,5,230,230), percent))
        self.total.setText(QApplication.translate("diskFull","Place totale : {size} kilo-octets",None, QApplication.UnicodeUTF8).format(size=total))
        self.used.setText(QApplication.translate("diskFull","Place utilisée : {size} kilo-octets",None, QApplication.UnicodeUTF8).format(size=used))

def sceneWithUsage(parent, rect, percent):
    """
    @param parent le widget père
    @param rect le QRect contenant la scène
    @param percent pourcentage utilisé
    @return une QGraphicsScene avec un symbole d'occupation du disque
    """
    scene=QGraphicsScene(parent)
    scene.addEllipse ( rect, QPen(), QBrush(QColor("lightyellow")) )
    usedEllipse=scene.addEllipse (rect, QPen(), QBrush(QColor("slateblue")) )
    usedEllipse.setStartAngle(0)
    usedEllipse.setSpanAngle(360 * 16 * percent / 100)
    return scene
