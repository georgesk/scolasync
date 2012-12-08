#!/usr/bin/python
# -*- coding: utf-8 -*-

licence={}
licence['en']="""
    file sconet.py
    this file is part of the project scolasync
    
    Copyright (C) 2012 Georges Khaznadar <georgesk@ofset.org>

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

import xml.dom.minidom

class Sconet:
    """
    Une classe pour travailler avec des données Sconet
    """

    def __init__(self, file):
        """
        Le constructeur
        @param file le nom d'un fichier, ou un fichier ouvert en lecture
        """
        if type(file)==type(""):
            try:
                # python3 way
                file=open(file, "r", encoding="iso-8859-1")
            except:
                # former way
                file=open(file, "r")
        self.donnees=xml.dom.minidom.parse(file)
        self.makeCompact()

    def makeCompact(self):
        """
        removes useless thext nodes containing only spaces.
        """
        self.nullTexts={}
        self.elementsWalk(self.donnees.documentElement, self.collectNullTexts)
        for el in self.nullTexts.keys():
            for e in self.nullTexts[el]:
                el.removeChild(e)

    def collectNullTexts(self,el):
        self.nullTexts[el]=[]
        for e in el.childNodes:
            if e.nodeType==e.TEXT_NODE and e.data.strip()=="":
                self.nullTexts[el].append(e)

    def collectClasses(self):
        """
        @return the list of classes containg students
        """
        self.classes=set()
        self.elementsWalk(self.donnees.documentElement, self.collectOneClass)
        return self.classes

    def collectOneClass(self,el):
        """
        @return the name of a class if it is a class with students
        """
        if el.nodeName.lower()=="structure":
            if el.getElementsByTagName("TYPE_STRUCTURE")[0].firstChild.data=="D":
                self.classes.add(el.getElementsByTagName("CODE_STRUCTURE")[0].firstChild.data)



    def elementsWalk(self, el, proc):
        """
        implemente un parcour des éléments d'un arbre, pour y appliquer
        une procédure
        @param el un élément
        @param proc la procédure à appliquer (paramètres : l'élément)
        """
        proc(el)
        for e in el.childNodes:
            self.elementsWalk(e, proc)

    def __str__(self):
        return self.donnees.toprettyxml(indent="  ",encoding="utf-8")


if __name__=="__main__":
    s=Sconet("../exemples/SCONET_test.xml")
    print (s.collectClasses())
