#!/usr/bin/python3
# -*- coding: utf-8 -*-
# 	$Id: scolasync.py 47 2011-06-13 10:20:14Z georgesk $	

"""@package scolasync
Scolasync est un programme pour gérer des transferts de fichiers entre un
ordinateur et une collection de clés USB.

"""

## \mainpage ScolaSync
#
# \section but But de l'application
#
# Scolasync est un programme pour gérer des transferts de fichiers
# entre un ordinateur et une collection de clés USB.
#
# \section CahierDeCharges CAHIER DE CHARGES DE SCOLASYNC
# 
# -# l'application doit pouvoir être utilisable par n'importe quel
# enseignant, par exemple un prof de langues quelques minutes après la
# prise en main.
# -# une personne-essource, ou le prof lui-même, doit pouvoir très
# simplement créer une association permanente entre les identifiants des
# clés USB et les noms d'élèves. Cette association doit pouvoir évoluer
# en fonction des classes à la demande de l'enseignant, d'une année sur
# l'autre, ou d'un cycle de travail à un autre.
# -# un prof doit pouvoir envoyer un ensemble de fichiers vers les clés
# USB de ses élèves identiquement pour tous. L'individualisation peut se
# faire en branchant/débranchant les clés. Le prof doit avoir la
# possibilité de choisir, voire de créer le dossier de réception.
# -# chaque élève doit pouvoir retrouver facilement ces fichiers et
# surtout la consigne expliquant ce qu'il doit faire, et comment il sera
# noté.  Comme les lecteurs mp3 stockent souvent des fichiers dans des
# répertoires de noms variés, il faut pouvoir gérer ça.
# -# le prof doit pouvoir récolter les clés USB des élèves et récupérer
# leur travail en quelques minutes seulement, par exemple en
# sélectionnant le dossier dans lequel se trouve le fichier à récupérer.
# -# l'application doit renommer les fichiers en tenant compte du nom du
# baladeur, donc du nom de l'élève.
# -# il faut pouvoir effacer des fichiers sur les clés, voire les
# remettre à zéro.
#
# \section licence Licence
#
# <b>ScolaSync version 1.0 :</b>
#
# un programme pour gérer des transferts de fichiers entre un
# ordinateur et une collection de clés USB.
# 
# <b>Copyright © 2010-2012 Georges Khaznadar <georgesk@ofset.org></b>
# 
# Ce projet est un logiciel libre : vous pouvez le redistribuer, le
# modifier selon les terme de la GPL (GNU Public License) dans les
# termes de la Free Software Foundation concernant la version 3 ou
# plus de la dite licence.
#
# Ce programme est fait avec l'espoir qu'il sera utile mais <b>SANS
# AUCUNE GARANTIE</b>. Lisez la <a href="http://www.gnu.org/licenses/"
# target="license">licence</a> pour plus de détails.
#
# \section support Support
#
# Si vous avez besoin d'un support pour ce programme, tel que :
# <b>garantie contractuelle</b>, <b>formation</b>, <b>adaptation plus
# précise</b> aux besoins de votre entreprise, etc. contactez
# l'association <a href="http://www.ofset.org"
# target="ofset">OFSET</a> et/ou <a
# href="mailto:georgesk@ofset.org">l'auteur</a> du logiciel.
#
# \section architecture Architecture de ScolaSync
#
# Scolasync est bâti sur des composants logiciels libres, les plus
# notables sont les suivants :
#
# - la bibliothèque Qt4 pour l'interface graphique
# - la bibliothèque python-dbus pour l'interaction avec le noyau Linux 2.6
# - la bibliothèque udisks pour interroger facilement le noyau sur le
# statut des disques, et pour réaliser certaines actions sur les
# disques et clés USB
# - l'utilisation de threads pour mener en parallèle les actions qui
# concernent simultanément plusieurs clés USB

licence={}
licenceEn="""
    scolasync version %s:

    a program to manage file transfers between a computer and a collection
    of USB sticks.
    
    Copyright (C) 2010-2012 Georges Khaznadar <georgesk@ofset.org>

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
    
    Copyright (C) 2010-2012 Georges Khaznadar <georgesk@ofset.org>
    
    Ce projet est un logiciel libre : vous pouvez le redistribuer, le
    modifier selon les terme de la GPL (GNU Public License) dans les
    termes de la Free Software Foundation concernant la version 3 ou
    plus de la dite licence.
    
    Ce programme est fait avec l'espoir qu'il sera utile mais SANS
    AUCUNE GARANTIE. Lisez la licence pour plus de détails.
    
    <http://www.gnu.org/licenses/>.
"""
licence['fr']=licenceFr


python3safe=True

import getopt, os, sys

import sip
# pour éviter des erreurs à l'instanciation des QVariant
sip.setapi('QVariant', 1)


from PyQt4.QtGui import *
from PyQt4.QtCore import *

def usage():
    """
    affiche le mode d'emploi à la console
    """
    print ("""\
"{args}" : une option n'est pas reconnue
Options :
 -c ou --check : pour que la première colonne du tableau comporte
    des cases à cocher.""".format(args=" ".join(sys.argv))
           )
    return

def run():
    """
    Le lancement de l'application
    """
    from dbus.mainloop.qt import DBusQtMainLoop
    DBusQtMainLoop(set_as_default=True)
    
    app = QApplication(sys.argv)

    args=sys.argv[1:]
    try:
        #opts,args= ["check"], sys.argv
        opts, args = getopt.getopt(args, "c", ["check"] )
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    locale = "%s" %QLocale.system().name()
    qtTranslator = QTranslator()
    if qtTranslator.load("qt_" + locale, "/usr/share/qt4/translations"):
        # print "OK for qttranslator"
        app.installTranslator(qtTranslator)
    appTranslator = QTranslator()
    langdir=os.path.join("lang",locale+".qm")
    b= appTranslator.load(langdir)
    if b:
        # print "installation du fichier de traduction", langdir
        app.installTranslator(appTranslator)

    import mainWindow
    windows = mainWindow.mainWindow(None,opts,locale)
    windows.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    run()
