#!/bin/bash

(cd pdfminer; python setup.py build)
pdfminer/build/scripts-2.7/pdf2txt.py  ~/store/statements/chase-7165/2014-07-18.pdf
