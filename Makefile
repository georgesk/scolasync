DESTDIR = 
SUBDIRS = src
DOCSRC = $(shell find src -name '*.py'| grep -v marques.py)
DB2MAN = /usr/share/sgml/docbook/stylesheet/xsl/docbook-xsl/manpages/docbook.xsl
XP     = xsltproc --nonet --param man.charmap.use.subset "0"

all: doxy pdfdoc scolasync.1
	for d in $(SUBDIRS); do make all -C $$d DESTDIR=$(DESTDIR); done

install:
	install -d $(DESTDIR)/usr/share/scolasync/html
	cp -R doc/html/* $(DESTDIR)/usr/share/scolasync/html/
	install -d $(DESTDIR)/usr/share/scolasync/pdf
	install -m 644 doc/latex/refman.pdf $(DESTDIR)/usr/share/scolasync/pdf
	install -d $(DESTDIR)/usr/share/scolasync/exemple
	install -m 644 exemples/* $(DESTDIR)/usr/share/scolasync/exemple
	for d in $(SUBDIRS); do make install -C $$d DESTDIR=$(DESTDIR); done
	install -d $(DESTDIR)/usr/bin
	install -m 755 scolasync $(DESTDIR)/usr/bin/scolasync
	install -d $(DESTDIR)/usr/share/applications
	install -m 644 scolasync.desktop $(DESTDIR)/usr/share/applications


scolasync.1: manpage.xml
	$(XP) $(DB2MAN) $<

doxy: doc/html/index.html

pdfdoc: doc/latex/refman.pdf

doc/latex/refman.pdf: $(DOCSRC) config.dox
	cd doc/latex/; sed 's/utf8\]/utf8x]/' refman.tex > refman.tex.tmp && \
	  mv refman.tex.tmp refman.tex
	cd doc/latex; pdflatex refman.tex; \
	while grep -q "Rerun to get" refman.log; do \
	  pdflatex refman.tex; \
	done


doc/html/index.html: $(DOCSRC) config.dox
	doxygen config.dox

clean:
	rm -f *~ *.1
	cd doc/latex; rm -f *.aux *.log *~ *.toc *.idx *.out
	for d in $(SUBDIRS); do make clean -C $$d DESTDIR=$(DESTDIR); done

distclean: clean
	rm -rf doc/latex doc/html
	for d in $(SUBDIRS); do make distclean -C $$d DESTDIR=$(DESTDIR); done

tgz: all clean
	d=$$(pwd); cd ..; tar czvf scolasync-$$(date +%Y%m%d).tgz $$d

dist: distclean
	d=$$(pwd); cd ..; tar czvf scolasync-source-$$(date +%Y%m%d).tgz $$d

PHONY: all doxy clean pdfdoc distclean tgz install


