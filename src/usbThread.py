# -*- coding: utf-8 -*-    
# $Id: usbThread.py 47 2011-06-13 10:20:14Z georgesk $	

licenceEn="""
    file usbThread.py
    this file is part of the project scolasync
    
    Copyright (C) 2010-2012 Georges Khaznadar <georgesk@ofset.org>

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

import subprocess, threading, re, os, os.path, shutil
import time, glob, shlex, io
from PyQt4.QtCore import *

_threadNumber=0

def ensureDirExists(destpath):
    """
    force l'existence d'un répertoire, récursivement si nécessaire
    @param destpath le chemin de ce répertoire
    """
    os.path.isdir(destpath) or os.makedirs(destpath, mode=0o755)
    return

class ThreadRegister:
    """
    Une classe pour tenir un registre des threads concernant les baladeurs.
    """

    def __init__(self):
        """
        Le constructure met en place un dictionnaire
        """
        self.dico={}

    def __str__(self):
        return "ThreadRegister: %s" %self.dico
        
    def push(self, ud, thread):
        """
        @param ud un disque
        @param thread un thread
        Empile un thread pour le baladeur ud
        """
        if ud.getOwner() not in self.dico.keys():
            self.dico[ud.getOwner()]=[thread]
        else:
            self.dico[ud.getOwner()].append(thread)

    def pop(self, ud, thread):
        """
        @param ud un disque
        @param thread un thread
        Dépile un thread pour le baladeur ud
        """
        self.dico[ud.getOwner()].remove(thread)

    def busy(self, owner):
        """
        Indique si le disque est occupé par des threads
        @param owner le propriétaire du disque
        @return les données associées par le dictionnaire
        """
        if owner in self.dico.keys():
            return self.dico[owner]
        return []

    def threadSet(self):
        """
        renvoie l'ensemble des threads actifs
        """
        result=set()
        for o in self.dico.keys():
            for t in self.dico[o]:
                result.add(t)
        return result
            
def _sanitizePath(path):
    """
    Évite d'avoir des <i>slashes</i> dans un nom de thread
    @return la fin du nom de chemin, après le dernier <i>slash</i> ;
    si le chemin ne finit pas bien, remplace les <i>slashes</i> par
    des sous-tirets "_".
    """
    pattern=re.compile(".*([^/]+)")
    m=pattern.match(str(path))
    if m:
        return m.group(1)
    else:
        return str(path).replace('/','_')

def _threadName(ud):
    """
    fabrique un nom de thread commençant par th_, suivi d'un nombre unique,
    suivi d'une chaîne relative à la clé USB
    @param ud une instance de uDisk
    @return un nom de thread unique
    """
    global _threadNumber
    if hasattr(ud, "path"):
        name="th_%04d_%s" %(_threadNumber,_sanitizePath(ud.path))
    else:
        name="th_%04d_%s" %(_threadNumber,"dummy")
    _threadNumber+=1
    return name

def _date():
    """
    Renvoie la date et l'heure dans un format court
    @return une chaîne donnée par strftime et le format %Y/%m/%d-%H:%M:%S
    """
    return time.strftime("%Y/%m/%d-%H:%M:%S")

class abstractThreadUSB(threading.Thread):
    """
    Une classe abstraite, qui sert de creuset pour les classe servant
    aux copies et aux effacements.

    Les classes filles doivent redéfinir la méthode \b toDo : c'est celle qui
    est démarrée quand le thread est lancé. Cette méthode est appelée dans
    le contexte « \b with ud.rlock », qui évite que deux threads en même temps
    ne cherchent à accéder au même média.

    Une méthode \b copytree est définie pour remplacer shutils.copytree
    qui ne fait pas tout à fait l'affaire.
    """
    def __init__(self,ud, fileList, subdir, dest=None, logfile="/dev/null",
                 parent=None):
        """
        Constructeur
        Crée un thread pour copier une liste de fichiers vers une clé USB.
        @param ud l'instance uDisk correspondant à une partition de clé USB
        @param fileList la liste des fichiers à traiter
        @param subdir un sous-répertoire de la clé USB
        @param dest un répertoire de destination si nécessaire, None par défaut
        @param logfile un fichier de journalisation, /dev/null par défaut
        @param parent un widget qui recevra de signaux en début et en fin
          d'exécution
        """
        threading.Thread.__init__(self, name=_threadName(ud))        
        self._args=(ud, fileList, subdir, dest, logfile)
        self.ud=ud
        if hasattr(ud,"threadRunning"): ud.threadRunning=True
        self.fileList=fileList
        self.subdir=subdir
        self.dest=dest
        self.logfile=logfile
        self.parent=parent

    def run(self):
        with self.ud.rlock:
            self.toDo(*self._args)

    def writeToLog(self, msg):
        """
        Écrit un message dans le fichier de journalisation
        @param msg le message
        """
        open(os.path.expanduser(self.logfile),"a").write(msg+"\n")
        return

    def copytree(self,src, dst, symlinks=False, ignore=None, erase=False, errors=[]):
        """
        Une version modifiée de shutil.copytree qui accepte que les
        repertoires destination soient déjà existants. Cette source dérive
        de la documentation fournie avec Python 2.7
        @param src un nom de fichier ou de répertoire
        @param dst un nom de de répertoire (déjà existant ou à créer)
        @param symlinks vrai si on veut recopier les liens tels quels
        @param ignore une fonction qui construit une liste de fichiers à ignorer (profil : répertoire, liste de noms de fichiers -> liste de noms de fichiers à ignorer)
        @param erase s'il est vrai la source est effacée après copie réussie
        @param errors la liste d'erreurs déjà relevées jusque là
        @return une liste d'erreurs éventuellement relevées, sinon une liste vide
        """
        names = os.listdir(src)
        if ignore is not None:
            ignored_names = ignore(src, names)
        else:
            ignored_names = set()

        try:
            os.makedirs(dst)
        except OSError as err:
            pass
        for name in names:
            if name in ignored_names:
                continue
            srcname = os.path.join(src, name)
            dstname = os.path.join(dst, name)
            try:
                if symlinks and os.path.islink(srcname):
                    linkto = os.readlink(srcname)
                    os.symlink(linkto, dstname)
                    if not errors and erase:
                        os.unlink(srcname)
                elif os.path.isdir(srcname):
                    errors=self.copytree(srcname, dstname,
                                         symlinks=symlinks, ignore=ignore,
                                         erase=erase, errors=errors)
                    if not errors and erase:
                        os.rmdir(srcname)
                else:
                    shutil.copy2(srcname, dstname)
                    if not errors and erase:
                        os.unlink(srcname)
                # XXX What about devices, sockets etc.?
            except IOError as why:
                errors.append((srcname, dstname, str(why)))
                # catch the Error from the recursive copytree so that we can
                # continue with other files
            except os.error as why:
                errors.append((srcname, dstname, str(why)))
                # catch the Error from the recursive copytree so that we can
                # continue with other files
            except Exception as err:
                errors.extend(err.args[0])
        return errors

    def __str__(self):
        """
        Renvoie une chaîne informative sur le thread
        @return une chaine donnant des informations sur ce qui va
        se passer dans le thread qui a été créé.
        """
        result="%s(\n" %self.threadType()
        result+="  ud       = %s\n" %self.ud
        result+="  fileList = %s\n" %self.fileList
        result+="  subdir   = %s\n" %self.subdir
        result+="  dest     = %s\n" %self.dest
        result+="  logfile  = %s\n" %self.logfile
        result+="\n"
        return result

    def threadType(self):
        """
        information sur le thread.
        @return une chaîne courte qui informe sur le type de thread
        """
        return "abstractThreadUSB"

    def toDo(self, ud, fileList, subdir, dest, logfile):
        """
        La fonction abstraite pour les choses à faire
        @param ud l'instance uDisk correspondant à une partition de clé USB
        @param fileList la liste des fichiers à traiter
        @param subdir un sous-répertoire de la clé USB
        @param dest un répertoire de destination
        @param logfile un fichier de journalisation
        """
        # ça ne fait rien du tout pour un thread abstrait
        pass

class threadCopyToUSB(abstractThreadUSB):
    """
    Classe pour les threads copiant vers les clés USB
    """
    def __init__(self,ud, fileList, subdir, logfile="/dev/null",
                 parent=None):
        """
        Constructeur
        Crée un thread pour copier une liste de fichiers vers une clé USB.
        @param ud l'instance uDisk correspondant à une partition de clé USB
        @param fileList la liste des fichiers à copier
        @param subdir le sous-répertoire de la clé USB où faire la copie
        @param logfile un fichier de journalisation, /dev/null par défaut
        @param parent un widget qui recevra de signaux en début et en fin
          d'exécution
        """
        abstractThreadUSB.__init__(self,ud, fileList, subdir, dest=None, logfile=logfile, parent=parent)

    def threadType(self):
        """
        @return une chaîne courte qui informe sur le type de thread
        """
        return "threadCopyToUSB"

    def toDo(self, ud, fileList, subdir, dest, logfile):
        """
        Copie une liste de fichiers vers une clé USB sous un répertoire donné.
         Ce répertoire est composé de ud.visibleDir() joint au
         sous-répertoire subdir.
         À chaque fichier ou répertoire copié, une ligne est journalisée dans le
         fichier de journal de l'application.
        @param ud l'instance uDisk correspondant à une partition de clé USB
        @param fileList la liste des fichiers à copier
        @param logfile un fichier de journalisation
        @param subdir le sous-répertoire de la clé USB où faire la copie
        """
        while subdir[0]=='/':
            subdir=subdir[1:]
        destpath=os.path.join(ud.ensureMounted(),ud.visibleDir(),subdir)
        ensureDirExists(destpath)
        # boucle de copie
        for f in fileList:
            cmd="Copie de {0} vers {1}".format(f, destpath)
            if self.parent:
                self.parent.emit(SIGNAL("pushCmd(QString, QString)"), ud.getOwner(), cmd)
            destpath1=os.path.join(destpath, os.path.basename(f))
            # copie d'arbre si on copie un répertoire, ou de simple fichier
            if os.path.isdir(f):
                errors=self.copytree(f, destpath1)
            else:
                errors=[]
                try:
                    shutil.copy2(f, destpath1)
                except Exception as err:
                    errors.append([f, destpath1, str(err)])
                    
            msg="[%s] " %_date()
            if not errors:
                msg+="Success: "
            else:
                msg+="Error: "
            msg+=cmd
            for e in errors:
                msg+= " <%s>" %str(e)
            if self.parent:
                self.parent.emit(SIGNAL("popCmd(QString, QString)"), ud.getOwner(), cmd)
            self.writeToLog(msg)
            
class threadCopyFromUSB(abstractThreadUSB):
    """
    Classe pour les threads copiant depuis les clés USB
    """
    def __init__(self,ud, fileList, subdir=".", dest="/tmp",
                 rootPath="/", logfile="/dev/null", parent=None):
        """
        Constructeur
        Crée un thread pour copier une liste de fichiers depuis une clé USB
        vers un répertoire de disque.
        @param ud l'instance uDisk correspondant à une partition de clé USB
        @param fileList la liste des fichiers à copier
        @param subdir le sous-répertoire de la clé USB d'où faire la copie
        @param dest un répertoire de destination
        @param logfile un fichier de journalisation, /dev/null par défaut
        @param parent un widget qui recevra de signaux en début et en fin
          d'exécution
        """
        abstractThreadUSB.__init__(self,ud, fileList, subdir, dest=dest,
                                   logfile=logfile, parent=parent)
        self.rootPath=rootPath

    def toDo(self, ud, fileList, subdir, dest, logfile):
        """
        Copie une liste de fichiers d'une clé USB sous un répertoire donné.
         À chaque fichier ou répertoire copié, une ligne est journalisée
         dans le fichier de journal de l'application.
        @param ud l'instance uDisk correspondant à une partition de clé USB
        @param fileList la liste des fichiers à copier, qui peut contenir des jokers
        @param dest un répertoire de destination
        @param logfile un fichier de journalisation
        @param subdir le sous-répertoire de la clé USB où faire la copie
        """
        for f in fileList:
            ## prend le fichier ou le répertoire sur le disque courant
            fromPath=os.path.join(ud.ensureMounted(), f)
            owner=ud.getOwner()
            ## personnalise le nom de la destination
            newName="%s_%s" %(owner,os.path.dirname(f))
            ## calcule le point de copie et le répertoire à créer s'il le faut
            toPath=os.path.join(dest,newName)
            # crée le répertoire cible si nécessaire
            ensureDirExists(toPath)
            cmd="Copie de {0} vers {1}".format(fromPath, toPath)
            if self.parent:
                self.parent.emit(SIGNAL("pushCmd(QString, QString)"), ud.getOwner(), cmd)
            destpath1=os.path.join(toPath, os.path.basename(f))
            if os.path.isdir(fromPath):
                errors=self.copytree(fromPath, destpath1)
            else:
                errors=[]
                try:
                    shutil.copy2(fromPath, destpath1)
                except Exception as err:
                    errors.extend((fromPath, destpath1, str(err)))
                    
            msg="[%s] " %_date()
            if not errors:
                msg += "Success: "
            else:
                msg += "Error:   "
            msg += cmd
            for e in errors:
                msg += " <%s>" %e
            if self.parent:
                self.parent.emit(SIGNAL("popCmd(QString, QString)"), ud.getOwner(), msg)
            self.writeToLog(msg)

class threadMoveFromUSB(abstractThreadUSB):
    """
    Classe pour les threads déplaçant des fichiers depuis les clés USB
    """
    def __init__(self,ud, fileList, subdir=".", dest="/tmp",
                 rootPath="/", logfile="/dev/null", parent=None):
        """
        Constructeur
        Crée un thread pour déplacer une liste de fichiers depuis une clé USB
        vers un répertoire de disque.
        @param ud l'instance uDisk correspondant à une partition de clé USB
        @param fileList la liste des fichiers à copier
        @param subdir le sous-répertoire de la clé USB d'où faire la copie
        @param dest un répertoire de destination
        @param logfile un fichier de journalisation, /dev/null par défaut
        @param parent un widget qui recevra de signaux en début et en fin
          d'exécution
        """
        abstractThreadUSB.__init__(self,ud, fileList, subdir, dest=dest,
                                   logfile=logfile, parent=parent)
        self.rootPath=rootPath

    def toDo(self, ud, fileList, subdir, dest, logfile):
        """
        Copie une liste de fichiers d'une clé USB sous un répertoire donné.
         Après chaque copie réussie la source est effacée.
         À chaque fichier ou répertoire copié, une ligne est journalisée
         dans le fichier de journal de l'application.
        @param ud l'instance uDisk correspondant à une partition de clé USB
        @param fileList la liste des fichiers à copier
        @param dest un répertoire de destination
        @param logfile un fichier de journalisation
        @param subdir le sous-répertoire de la clé USB où faire la copie
        """
        for f in fileList:
            ## prend le fichier ou le répertoire sur le disque courant
            fromPath=os.path.join(ud.ensureMounted(), f)
            owner=ud.getOwner()
            ## personnalise le nom de la destination
            newName="%s_%s" %(owner,os.path.dirname(f))
            ## calcule le point de copie et le répertoire à créer s'il le faut
            toPath=os.path.join(dest,newName)
            # crée le répertoire cible si nécessaire
            ensureDirExists(toPath)
            cmd="copying %s to %s" %(fromPath, toPath)
            if self.parent:
                self.parent.emit(SIGNAL("pushCmd(QString, QString)"), ud.getOwner(), cmd)
            destpath1=os.path.join(toPath, os.path.basename(f))
            if os.path.isdir(fromPath):
                errors=self.copytree(fromPath, destpath1, erase=True)
                try:
                    os.rmdir(fromPath)
                except Exception as err:
                    errors.extend((fromPath, destpath1, str(err)))
            else:
                errors=[]
                try:
                    shutil.copy2(fromPath, destpath1)
                    os.unlink(fromPath)
                except Exception as err:
                    errors.extend((fromPath, destpath1, str(err)))
                    
            msg="[%s] " %_date()
            if not errors:
                msg += "Success: "
            else:
                msg += "Error:   "
            msg += cmd
            for e in errors:
                msg += " <%s>" %e
            if self.parent:
                self.parent.emit(SIGNAL("popCmd(QString, QString)"), ud.getOwner(), msg)
            self.writeToLog(msg)

class threadDeleteInUSB(abstractThreadUSB):
    """
    Classe pour les threads effaçant des sous-arbres dans les clés USB
    """
    def __init__(self,ud, fileList, subdir, logfile="/dev/null",
                 parent=None):
        """
        Constructeur
         Crée un thread pour supprimer une liste de fichiers dans une clé USB.
        @param ud l'instance uDisk correspondant à une partition de clé USB
        @param fileList la liste des fichiers à supprimer
        @param subdir le sous-répertoire de la clé USB où faire les suppressions
        @param logfile un fichier de journalisation, /dev/null par défaut
        @param parent un widget qui recevra de signaux en début et en fin
          d'exécution
        """
        abstractThreadUSB.__init__(self,ud, fileList, subdir, dest=None,
                                   logfile=logfile, parent=parent)

    def toDo(self, ud, fileList, subdir, dest, logfile):
        """
        Supprime une liste de fichiers dans une clé USB.
         La liste est prise sous un répertoire donné. Le répertoire visible
         qui dépend du constructuer d ela clé est pris en compte.
         À chaque fichier ou répertoire supprimé, une ligne est
         journalisée dans le fichier de journal de l'application.
        @param l'instance uDisk correspondant à une partition de clé USB
        @param fileList la liste des fichiers à copier
        @param dest un répertoire de destination
        @param logfile un fichier de journalisation
        @param subdir le sous-répertoire de la clé USB où faire la copie
        """
        for f in fileList:
            toDel=os.path.join(ud.ensureMounted(), f)
            cmd="Effacement de {0}".format(toDel)
            errors=[]
            if self.parent:
                self.parent.emit(SIGNAL("pushCmd(QString, QString)"), ud.getOwner(), cmd)
            if os.path.isdir(toDel):
                try:
                    for root, dirs, files in os.walk(toDel, topdown=False):
                        for name in files:
                            os.remove(os.path.join(root, name))
                        for name in dirs:
                            os.rmdir(os.path.join(root, name))
                    os.rmdir(toDel)
                except Exception as err:
                    errors.expand((toDel,str(err)))
            else:
                try:
                    os.unlink(toDel)
                except Exception as err:
                    errors.expand((toDel,str(err)))
            msg="[%s] " %_date()
            if not errors:
                msg += "Success: "
            else:
                msg += "Error:   "
            msg += cmd
            for e in errors:
                msg += " <%s>" %e
            if self.parent:
                self.parent.emit(SIGNAL("popCmd(QString, QString)"), ud.getOwner(), msg)
            self.writeToLog(msg)

if __name__=="__main__":
    import sys, ownedUsbDisk, subprocess

    def test_copytree():
        """ Teste la fonction copytree """
        t=abstractThreadUSB(None, sys.argv[1:-1], sys.argv[-1])
        if len(sys.argv) < 3:
            print("Usage : %s répertoire_source répertoire_destination" %sys.argv[0])
            print("Ça doit créer sous répertoire_destination la même arborescence que sous répertoire_source")
            print("et ça crée répertoire_destination à la volée si nécessaire.")
            sys.exit(-1)
        errors=t.copytree(sys.argv[1],sys.argv[2])
        print("Erreurs = %s" %errors)
        subprocess.call ("diff -ruN %s %s" %(sys.argv[1],sys.argv[2]), shell=True)
        print ("Ne pas oublier d'effacer %s si nécessaire" %sys.argv[2])

    def test_copy2():
        """
        Teste la copie d'un fichier vers une destination telle qu'elle est pratiquée
        dans la méthode copytree de abstractThreadUSB
        """
        if len(sys.argv) < 3:
            print("Usage : %s fichier répertoire_destination" %sys.argv[0])
            print("Ça doit créer sous répertoire_destination une copie du fichier")
            print("et ça crée répertoire_destination à la volée si nécessaire.")
            sys.exit(-1)
        srcname=sys.argv[1]
        dstname=os.path.join(sys.argv[2],sys.argv[1])
        shutil.copy2(srcname, dstname)
        print ("fin de la copie de %s vers %s, listing de %s" %(sys.argv[1],sys.argv[2],sys.argv[2]))
        subprocess.call("ls %s" %sys.argv[2], shell=True)

    #test_copytree()
    test_copy2()
