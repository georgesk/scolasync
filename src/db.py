# 	$Id: db.py 47 2011-06-13 10:20:14Z georgesk $	

licence={}
licence['en']="""
    file db.py
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

import os.path, sqlite3, subprocess
import version
from globaldef import userShareDir

database= None # base de données sqlite 3 commune à tous les modules
cursor=None

def openDb():
    """
    Ouverture de la base de données de l'application, et création si nécessaire.
    @return une instance de base de données sqlite3
    """
    global database, cursor
    dir=os.path.expanduser(userShareDir)
    if not os.path.isdir(dir):
        subprocess.call("mkdir %s" %dir, shell=True)
    database = sqlite3.connect(os.path.join(dir,"db"))
    cursor=database.cursor()
    cursor.execute('''create table if not exists owners (stickid text, uuid text, tatoo text, student text)''')
    cursor.execute('''create table if not exists version (major text, minor text)''')
    cursor.execute('''create table if not exists preferences (checkable int, mv int, schoolfile text, workdir text, manfile text)''')
    database.commit()
    checkVersion(version.major(), version.minor())

def checkVersion(major, minor):
    """
    Vérifie si la base de données reste compatible.
    Un changement de version majeur implique une mise à jour en cas de
    base de donnée ancienne. Un changmeent de version mineur n'implique
    pas de changement de structure de la base de données.
    """
    cursor.execute('''select * from version''')
    values=cursor.fetchone()
    if values == None:
        # pas de version existante, on la crée
        cursor.execute('''insert into version values (?,?)''', (version.major(), version.minor()))
    else:
        major, minor = values
        if major < version.major():
            raise KeyError("The database version is too old!")
        elif minor < version.minor():
            cursor.execute("""update version
                          set minor=?
                          where major=?""", (version.minor(), version.major()))
    database.commit()

def hasStudent(student):
    """
    vérifie qu'un étudiant est déjà connu
    @param student propriétaire du baladeur
    @return True si le propriétaire existe déjà
    """
    global cursor
    cursor.execute("select * from owners where student=?", (student,))
    return cursor.fetchone() != None
    
def knowsId(stickid, uuid,tattoo):
    """
    dit si une clé USB est déjà connue
    @param stickid un identifiant de baladeur
    @param uuid un identifiant de partition
    @param tattoo un tatouage de partition
    @return un booléen vrai si la clé USB est connue, faux sinon
    """
    global cursor
    cursor.execute("select * from owners where stickid=? and uuid=? and tatoo=?", (stickid, uuid,tattoo))
    return cursor.fetchone() != None

def tattooList():
    """
    Renvoie la liste des tatouages connus de la base de données
    """
    global cursor
    cursor.execute("select tatoo from owners")
    return cursor.fetchmany()
    
def readStudent(stickid, uuid, tattoo):
    """
    renvoie l'étudiant qui possède une clé USB
    @return un nom d'étudiant ou None si la clé est inconnue
    """
    global cursor
    cursor.execute("select student from owners where stickid=? and uuid=? and tatoo=?", (stickid, uuid,tattoo))
    s = cursor.fetchone()
    if s != None:
        return s[0]
    else:
        return None

def readPrefs():
    """
    renvoie les préférences de ScolaSync
    @return un dictionnaire de préférences
    """
    global cursor
    cursor.execute("select checkable, mv, schoolfile,workdir, manfile from preferences")
    s = cursor.fetchone()
    if s != None:
        checkable      = s[0]==1
        mv             = s[1]==1
        schoolFile     = s[2]
        workdir        = s[3]
        manfile        = s[4]
        return {"checkable"     : checkable,
                "mv"            : mv,
                "schoolFile"    : schoolFile,
                "workdir"       : workdir,
                "manfile"       : manfile,
                }
    else:
        # valeur par défaut si la base est vide de préférences
        return {"checkable"     : True,
                "mv"            : False,
                "schoolFile"    : "/usr/share/scolasync/exemple/SCONET_test.xml",
                "workdir"       : "Travail",
                "manfile"       : "/usr/share/scolasync/help/manualPage_fr_FR.html",
                }

def setWd(newDir):
    """
    définit le nouveau nom du répertoire de travail préféré.
    """
    cursor.execute("""update preferences set workdir=?""",
                   (newDir,))
    database.commit()

def writeStudent(stickid, uuid, tattoo, student):
    """
    inscrit un étudiant comme propriétaire d'une clé USB
    @param student un nom d'étudiant
    """
    global database, cursor
    if knowsId(stickid, uuid, tattoo):
        cursor.execute("""update owners
                          set student=?
                          where stickid=? and uuid=? and tatoo=?""", (student, stickid, uuid, tattoo))
    else:
        cursor.execute("""insert into owners
                          values (?,?,?,?)""", (stickid, uuid, tattoo, student))
    database.commit()

def writePrefs(prefs):
    """
    inscrit les préférences
    @param prefs un dictionnaire {"checkable": booléen toujours vrai, "workdir" : le répertoire préféré pour les fichiers de travail}
    """
    global database, cursor
    checkable=1
    if prefs["mv"]:
        mv=1
    else:
        mv=0
    cursor.execute("select checkable from preferences")
    s = cursor.fetchone()
    newValues=(1, mv, prefs["schoolFile"], prefs["workdir"], prefs["manfile"])
    if s != None:
        cursor.execute("""update preferences
                          set checkable=?, mv=?, schoolfile=?, workdir=?, manfile=?""",
                       newValues)
    else:
        cursor.execute("""insert into preferences
                          values (?,?,?,?,?)""",
                       newValues)
    database.commit()


if database == None:
    openDb()
