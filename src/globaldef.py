#!/usr/bin/python
# 	$Id: globaldef.py 47 2011-06-13 10:20:14Z georgesk $	

"""
globaldef.py is part of the package scolasync. This module contains
some definitions which can be reused globally in the application
"""

licenceEn="""
    scolasync version %s:

    a program to manage file transfers between a computer and a collection
    of USB sticks.
    
    Copyright (C) 2010 Georges Khaznadar <georgesk@ofset.org>

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

import platform, os

if platform.system()=="Linux":
    userShareDir="~/.scolasync"
    logFileName="~/.scolasync/scolasync.log"
    markFileName="~/.scolasync/marques.py"
elif platform.system()=="Windows":
    # to be implemented
    userShareDir="??"
    logFileName="??"
    markFileName="??"
    
def firstdir(l):
    """
    Renvoie le premier répertoire existant d'une liste de propositions
    @param l la liste de propositions
    """
    for d in l:
        if os.path.isdir(d): return d
    return None
   
def _dir(which):
    """
    Renvoie le répertoire où trouver telle ou telle ressource
    @param which le type de ressource
    """
    if which=="lang":
        return firstdir(["/usr/share/scolasync/lang", "lang"])
    elif which=="help":
        return firstdir(["/usr/share/scolasync/help", "help"])
    elif which=="share":
        return firstdir(["/usr/share/scolasync/","share"])
    return None

