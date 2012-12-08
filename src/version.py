# -*- coding: utf-8 -*-    
# 	$Id: version.py 43 2011-01-15 23:12:57Z georgesk $	

licence={}
licence['en']="""
    file version.py
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

def major():
    """
    @return le numéro majeur de version
    """
    return "3"

def minor():
    """
    @return le numéro mineur de version
    """
    return "1"

def version():
    """
    @return l'identifiant de la version
    """
    return "%s.%s" %(major(), minor())

