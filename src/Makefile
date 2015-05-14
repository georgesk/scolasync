DESTDIR = 
HELPFILES = $(shell ls help | grep -E 'xhtml$$|css$$|png$$')
SOURCES = $(shell ls *.py| grep -v marques.py)
ITF_SOURCES = $(shell ls *.ui)
ITF = $(patsubst %.ui, Ui_%.py, $(ITF_SOURCES))

test: clean all
	# crée des liens symboliques pour faciliter les tests
	ln -s /usr/share/icons/Tango/16x16 images/icons16
	ln -s /usr/share/icons/Tango/32x32 images/icons32

all: interfaces
	make -C lang all

interfaces: $(ITF)

Ui_%.py: %.ui
	pyuic5 $< > $@

clean:
	rm -rf build __pycache__
	# effacement des liens symboliques utilisés pour les tests
	rm -f images/icons*
	rm -f *~ Ui_* *.pyc
	make -C lang clean

distclean: clean

install:
	install -d $(DESTDIR)/usr/share/scolasync
	install -m 644 marques.py $(SOURCES) $(DESTDIR)/usr/share/scolasync
	# corrige les chemins dans les fichiers d'interface utilisateur
	# pour faire des chemins absolus
	for f in $(ITF); do \
	  sed -e 's%images%/usr/share/scolasync/images%' \
	    $$f > $(DESTDIR)/usr/share/scolasync/$$f; done
	install -d $(DESTDIR)/usr/share/scolasync/lang
	install -m 644 lang/*.qm $(DESTDIR)/usr/share/scolasync/lang
	install -d $(DESTDIR)/usr/share/scolasync/images
	install -m 644 images/* $(DESTDIR)/usr/share/scolasync/images
	install -d $(DESTDIR)/usr/share/scolasync/help
	install -m 644 help/* $(DESTDIR)/usr/share/scolasync/help

svn-keywords:
	for f in $(SOURCES); do svn propset svn:keywords "Id" $$f; done

PHONY: all interfaces clean distclean svn-keywords install test

