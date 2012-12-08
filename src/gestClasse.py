#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Ce module permet de gérer des classes d'élèves. La classe
AbstractGestClasse définit les fonctions minimales à implémenter
pour chaque gestionnaire de classes.
"""

licence={}
licence['en']="""
    file gestClasse.py
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

import xml.dom.minidom, copy

class AbstractGestClasse:
    def __init__(self,f):
        """
        le constructeur
        @param f le nom d'un fichier, ou un fichier ouvert en lecture
        qui contient les données permettant la gestion des classes d'un
        établissement scolaire
        """
        return

    def collectClasses(self):
        """
        @return une liste de noms de classes d'un établissement scolaire
        """
        return []

    def elevesDeClasse(self, cl):
        """
        @param cl une classe dans un établissement scolaire
        @return une liste d'élèves (sous forme d'objets)
        """
        return[]

    def unique_name(self, el):
        """
        @param el un objet élève
        @return une chaîne unicode, unique dans l'établissement
        """
        return "Cette fonction est abstraite, ne l'appelez pas ainsi."

    def showable_name(self,el):
        """
        @param el un objet élève
        @return une chaîne unicode, pour nommer l'élève
        """
        return "Cette fonction est abstraite, ne l'appelez pas ainsi."

class Sconet(AbstractGestClasse):
    """
    Une classe pour travailler avec des données Sconet
    """

    def __init__(self, f):
        """
        Le constructeur
        @param f le nom d'un fichier, ou un fichier ouvert en lecture
        """
        AbstractGestClasse.__init__(self,f)
        if type(f)==type(""):
            try:
                # python3 way
                file=open(f, "r", encoding="iso-8859-1")
            except:
                # former way
                file=open(f, "r")
        self.donnees=xml.dom.minidom.parse(f)
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

    def elevesDeClasse(self, className):
        """
        @param className name of a school class
        @return list of "eleve" elements
        """
        self.currentResult=[]
        self.currentClassName=className
        self.elementsWalk(self.donnees.documentElement, self.unIDEleveDeClasse)
        ids=copy.copy(self.currentResult)
        self.currentResult=[]
        for i in ids:
            self.currentID=i
            self.elementsWalk(self.donnees.documentElement, self.eleveParID)
        return copy.copy(self.currentResult)

    def eleveParID(self,el):
        """
        appends the "eleve" element to the list self.currentResult if
        self.currentID is matched

        """
        if  el.nodeName.lower()=="eleve" and el.getAttribute("ELEVE_ID")==self.currentID:
            self.currentResult.append(el)

    def unIDEleveDeClasse(self, el):
        """
        appends the ID of an "eleve" to self.currentResult if he belongs to
        the class self.currentClassName
        @param el an element
        """
        if  el.nodeName.lower()=="structures_eleve":
            structures=el.getElementsByTagName("STRUCTURE")
            if len (structures) > 0:
                if structures[0].getElementsByTagName("TYPE_STRUCTURE")[0].firstChild.data=="D":
                    if structures[0].getElementsByTagName("CODE_STRUCTURE")[0].firstChild.data==self.currentClassName:
                        idEleve=el.getAttribute("ELEVE_ID")
                        self.currentResult.append(idEleve)

    def collectOneClass(self,el):
        """
        adds one class name to the set self.classes
        @param el an element
        """
        if el.nodeName.lower()=="structure":
            if el.getElementsByTagName("TYPE_STRUCTURE")[0].firstChild.data=="D":
                self.classes.add(el.getElementsByTagName("CODE_STRUCTURE")[0].firstChild.data)


    def unique_name(self, el, fields=["NOM", "PRENOM"]):
        """
        a unique name for an "eleve", based on a few fields and on the ID
        @param el en "eleve" element
        @param fields the fields used to build the result
        @retun a printable unique id
        """
        items=[]
        for f in fields:
            items.append(el.getElementsByTagName(f)[0].firstChild.data)
        items.append(el.getAttribute("ELEVE_ID"))
        return "_".join(items)

    def showable_name(self,el, fields=["NOM", "PRENOM"]):
        """
        @param el un objet élève
        @param fields les champs de donnée à exploiter
        @return une chaîne unicode, pour nommer l'élève
        """
        items=[]
        for f in fields:
            items.append(el.getElementsByTagName(f)[0].firstChild.data)
        return " ".join(items)


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

