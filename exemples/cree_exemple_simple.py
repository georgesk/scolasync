#!/usr/bin/python3

import sys

def ecrit_entete(out):
    entete="""\
<?xml version="1.0" encoding="ISO-8859-1"?>
<BEE_ELEVES VERSION="1.7">
  <DONNEES>
"""
    out.write(entete)
    return

def ecrit_fin(out):
    fin="""\
  </DONNEES>
</BEE_ELEVES>
"""
    out.write(fin)
    return

def donnees(out, n):
    out.write("    <ELEVES>\n")
    for i in range(1,1+n):
        out.write("      <ELEVE ELEVE_ID=\"%d\">\n" %(1000+i))
        out.write("        <NOM>N°</NOM>\n")
        out.write("        <PRENOM>{0:02d}</PRENOM>\n".format(i))
        out.write("      </ELEVE>\n")
    out.write("    </ELEVES>\n")
    out.write("    <STRUCTURES>\n")
    for i in range(1,1+n):
        out.write("      <STRUCTURES_ELEVE ELEVE_ID=\"%d\">\n" %(1000+i))
        out.write("        <STRUCTURE>\n")
        out.write("          <CODE_STRUCTURE>Suite de numéros</CODE_STRUCTURE>\n")
        out.write("          <TYPE_STRUCTURE>D</TYPE_STRUCTURE>\n")
        out.write("        </STRUCTURE>\n")
        out.write("      </STRUCTURES_ELEVE>\n")
    out.write("    </STRUCTURES>\n")

if __name__=="__main__":
    out=open(sys.argv[1], "w", encoding="latin-1")
    ecrit_entete(out)
    donnees(out, 35)
    ecrit_fin(out)
    out.close()

        
