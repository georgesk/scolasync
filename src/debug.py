#!/usr/bin/python3

"""
Ce module facilite le debogage
"""

licence={}
licenceEn="""
    scolasync version %s:

    a program to manage file transfers between a computer and a collection
    of USB sticks.
    
    Copyright (C) 2010-2013 Georges Khaznadar <georgesk@debian.org>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
licence['en']=licenceEn

licenceFr="""
    scolasync version %s :

    un programme pour gérer des transferts de fichiers entre un
    ordinateur et une collection de clés USB.
    
    Copyright (C) 2010-2013 Georges Khaznadar <georgesk@debian.org>
    
    Ce projet est un logiciel libre : vous pouvez le redistribuer, le
    modifier selon les terme de la GPL (GNU Public License) dans les
    termes de la Free Software Foundation concernant la version 3 ou
    plus de la dite licence.
    
    Ce programme est fait avec l'espoir qu'il sera utile mais SANS
    AUCUNE GARANTIE. Lisez la licence pour plus de détails.
    
    <http://www.gnu.org/licenses/>.
"""
licence['fr']=licenceFr

from PyQt4.QtGui import *
from PyQt4.QtCore import *

def button(w, cb):
    """
    ajoute un bouton de débogage dans une fenêtre
    @param w la fenêtre
    @param cb une fonction de rappel à effectuer; celle ci
    accepte w comme premier paramètre
    """
    def cbWrapper():
        """
        fonction pour passer la paramètre mw à la fonction de rappel cb
        """
        cb(w)
        return

    b=QPushButton("Debug",w)
    b.connect(b, SIGNAL("clicked()"), cbWrapper)
    b.show()
    return

def listePartitionsCochees(w):
    """
    renseigne sur la liste des partions cochées de la fenêtre principale
    @param w la fenêtre principale
    """
    print (w.t)
