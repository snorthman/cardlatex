import re, subprocess, os, math
from decimal import Decimal
from pathlib import Path
from typing import List

from pikepdf import Pdf, Page, Rectangle

from . import PaperEnum


def unit_to_cm(unit: Decimal):
    return float(unit) * (1 / 72) * 2.54


def cm_to_unit(cm: float):
    return Decimal((cm / 2.54) * 72)


A4 = Rectangle(0, 0, cm_to_unit(21), cm_to_unit(29.7))
A3 = Rectangle(0, 0, cm_to_unit(29.7), cm_to_unit(42))


def find_crop(paper_sz, box_sz):
    crop = 0
    m = math.ceil(paper_sz / box_sz)
    while paper_sz / (box_sz - float(crop * 2)) < m:
        crop += cm_to_unit(0.1)
    if crop > cm_to_unit(0.5):
        m = m - 1
    return float(crop), m


def combine_pdf(*files: Path) -> Path:
    pdfs = [Pdf.open(file) for file in files]
    pdf_output = Pdf.new()

    for pdf in pdfs:
        for page in pdf.pages:
            pdf_output.pages.append(page)
        pdf.close()

    pdf_output.save(files[0])
    return files[0]


def grid_pdf(file: Path, has_back: bool = False):
    if not file.exists():
        raise FileNotFoundError(f'input pdf not found: ' + str(file))

    pdf = Pdf.open(file)
    pages: List[Page] = list(pdf.pages)

    if len({Rectangle(p.mediabox) for p in pages}) > 1:
        raise NotImplementedError('Cannot handle more than one card size.')

    box = Rectangle(pages[0].mediabox)
    for paper in [A4, A3]:
        x_crop, x_max = find_crop(paper.width, box.width)
        y_crop, y_max = find_crop(paper.height, box.height)
        if x_max == 0 or y_max == 0:
            [p.rotate(90, True) for p in pages]
            x_crop, x_max = find_crop(paper.width, box.height)
            y_crop, y_max = find_crop(paper.height, box.width)
        if x_max > 0 and y_max > 0:
            break

    if x_max == 0 or y_max == 0:
        raise ValueError('does not fit on A4 or A3')

    grid = x_max * y_max
    front, back = [[]], [[]]
    sheets = []
    for pp in range(len(pages)):
        l = back if pp % 2 == 1 and has_back else front
        if len(l[-1]) >= grid:
            sheets.append(l[-1])
            l.append([])
        l[-1].append(pp)
        pp += 1
    sheets.extend([f_b for f_b in [front[-1], back[-1]] if f_b])

    pdf_output = Pdf.new()

    rect_width = box.width - x_crop * 2
    rect_height = box.height - y_crop * 2
    x_offset = rect_width * (paper.width / rect_width - x_max) / 2
    y_offset = rect_height * (paper.height / rect_height - y_max) / 2
    for sheet in sheets:
        x, y = x_offset, y_offset
        new_page = pdf_output.add_blank_page(page_size=(paper.width, paper.height))
        for i, p in enumerate(sheet, 1):
            rect = Rectangle(x, y, x + rect_width, y + rect_height)
            new_page.add_overlay(pages[p], rect, push_stack=True, shrink=False, expand=False)
            x += rect_width
            if i % x_max == 0:
                x = x_offset
                y += rect_height

    pdf.close()
    pdf_output.save(file)
