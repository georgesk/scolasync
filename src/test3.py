#!/usr/bin/python3

import os, os.path, re

python3safe=True

if __name__=="__main__":
    files=os.listdir(".")
    pattern=re.compile(".*\.py$")
    files = [f for f in files if pattern.search(f) and "Ui_" not in f]
    safe=[]
    notsafe=[]
    for f in files:
        moduleName=f.replace(".py","")
        try:
            module=__import__(moduleName)
            if module.python3safe:
                safe.append(f)
        except:
            notsafe.append(f)
    print ("Safe modules"); print(safe)
    print ("UnSafe modules"); print (notsafe)

