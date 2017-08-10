#!/usr/bin/env python3
"""Morning Star PDF edition

Usage:
    pdf_edition.py DATE

DATE should be in %Y-%m-%d format (2017-12-31).
"""

from datetime import datetime
import logging
from pathlib import Path
import subprocess
import sys

from docopt import docopt
import msutils
import msutils.edition

logging.basicConfig(level=logging.INFO)

_server_remote_path = Path('/Volumes/Server/')
_server_local_path = Path('~/Server/').expanduser()
if _server_remote_path.exists():
    SERVER_PATH = _server_remote_path
elif _server_local_path.exists():
    SERVER_PATH = _server_local_path
else:
    logging.critical("Can't find server location.")
    sys.exit(1)

COMBINED_PDF_TEMPLATE = '{page.date:MS_%Y_%m_%d.pdf}'


as_export_pdf = '''\
on export_pdf(posix_path, pdf_export_file, page_to_export)
	tell application "Adobe InDesign CS4"
		-- Suppress dialogs
		set user interaction level of script preferences to never interact

		set smallestSize to PDF export preset "MS E-Edition"

		open (POSIX file posix_path as alias)

		tell PDF export preferences to set page range to page_to_export
		export the active document format PDF type to POSIX file pdf_export_file using smallestSize

		close the active document

		-- Restore dialogs
		set user interaction level of script preferences to interact with all
	end tell
end export_pdf

on run {{}}
	export_pdf("{indesign_file}", "{pdf_file}", "{page_to_export}")
end run
'''


def run_applescript(script: str):
    """Run an AppleScript using subprocess and osascript"""
    result = subprocess.run(
        args=['osascript', '-'],
        input=script,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8')
    if result.stderr:
        logging.error('AppleScript stderr: %s', result.stderr.rstrip())
    return result.stdout.rstrip()


def export_indesign_page(page, date):
    """Export an InDesign page using the as_export_pdf AppleScript"""
    pdfs_dir = msutils.edition._edition_subdirectory(
        date, msutils.edition.WEB_PDFS_TEMPLATE)
    pdfs_dir.mkdir(exist_ok=True)

    if len(page.pages) == 1:
        export_nums = [1]
        export_names = [page.path.with_suffix('.pdf').name]
    else:
        export_nums = [2, 3]
        export_names = []
        nums_str = '-'.join(map(str, page.pages))
        for pn in page.pages:
            new_name = page.path.with_suffix('.pdf').name
            new_name = new_name.replace(nums_str, str(pn), 1)
            export_names.append(new_name)

    for indd_page_num, pdf_name in zip(export_nums, export_names):
        run_applescript(as_export_pdf.format(
            indesign_file=page.path,
            pdf_file=pdfs_dir.joinpath(pdf_name),
            page_to_export=indd_page_num
            ))
        logging.info('Exported PDF file: %24s', pdf_name)


def export_with_ghostscript(export_file, *pdf_paths):
    args = [
        'gs',
        '-sDEVICE=pdfwrite',
        '-dPDFSETTINGS=/screen',
        '-dCompatibilityLevel=1.5',
        '-dNOPAUSE', '-dQUIET', '-dBATCH',
        '-sOutputFile=' + str(export_file)]

    args.extend([str(p) for p in pdf_paths])
    subprocess.run(args)


def save_combined_pdf(date):
    """Combine the web PDF files for date's edition using ghostscript"""
    files = msutils.edition_web_pdfs(date)
    if not files:
        logging.error('No web PDF files found for ghostscript step')
        sys.exit(1)
    combined_file = SERVER_PATH.joinpath(
        'Web PDFs',
        COMBINED_PDF_TEMPLATE.format(page=files[0]))

    export_with_ghostscript(combined_file, *[f.path for f in files])


def in_place_reduce_size(pdf_path):
    """Replace a PDF file with a reduced-size version"""
    tmp_name = pdf_path.with_name(pdf_path.name + '.tmp')
    export_with_ghostscript(tmp_name, pdf_path)
    tmp_name.replace(pdf_path)

if __name__ == '__main__':
    edition_date = datetime.strptime(docopt(__doc__)['DATE'], '%Y-%m-%d')
    files = msutils.edition_indd_files(edition_date)
#    for f in files: export_indesign_page(f, edition_date)
#    save_combined_pdf(edition_date)
    for p in msutils.edition_web_pdfs(edition_date):
        in_place_reduce_size(p.path)
