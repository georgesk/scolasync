class usbT:
    def __init__(self):
        return
    
    def threadCopyToUSB(self,p,l,subdir='', logfile='', parent=None):
        return "resultat"
    
class machin:
    def __init__(self):
        self.tm="coucouLeParent"
        p="le p"
        usbThread=usbT()
        cmd="usbThread.threadCopyToUSB(p,['/home/georgesk/2011-10-17-112913_1024x600_scrot.png'],subdir='Travail', logfile='~/.scolasync/scolasync.log', parent=self.tm)"
        t=eval(cmd)
        print(t)

m=machin()
