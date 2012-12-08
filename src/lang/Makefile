SOURCES = $(shell find .. -name "*.py"| grep -v marques.py| grep -v "^Ui_")
FORMS = $(shell find .. -name "*.ui")
TRANSLATIONS = $(shell ls *.ts)
LRELEASE = lrelease-qt4
LUPDATE = pylupdate4

all: scolasync.pro
	$(LUPDATE) -verbose $<
	$(LRELEASE) *.ts 2>/dev/null || true

scolasync.pro:
	echo "SOURCES = " $(SOURCES) > $@
	echo "FORMS = " $(FORMS) >> $@
	echo "TRANSLATIONS = " $(TRANSLATIONS) >> $@

clean:
	rm -f *~ scolasync.pro *.qm

.PHONY: clean all
