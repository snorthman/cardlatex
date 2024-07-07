import math
import logging
from decimal import Decimal
from pathlib import Path
from typing import List

from pikepdf import Pdf, Page, Rectangle


def unit_to_cm(unit: Decimal):
    return float(unit) * (1 / 72) * 2.54


def cm_to_unit(cm: float):
    return Decimal((cm / 2.54) * 72)


A4 = Rectangle(0, 0, cm_to_unit(21), cm_to_unit(29.7))
A3 = Rectangle(0, 0, cm_to_unit(29.7), cm_to_unit(42))


def find_fit(big_box, small_box):
    margins = [float(cm_to_unit(2.54 / _)) for _ in (2, 4)]

    # Initialize values
    best_n = 0
    best_margin = 0
    best_spacing = 0

    for margin in margins:
        # Calculate the number of small boxes that fit in the big box with the current margin
        remaining_space = big_box - 2 * margin
        n = math.floor(remaining_space / small_box)
        if n == 0:
            continue

        remaining_space -= n * small_box
        if n > 1:
            spacing = remaining_space / (n - 1)
        else:
            spacing = remaining_space / 2

        if n > best_n:
            best_n = n
            best_margin = margin
            best_spacing = spacing

    if best_n == 0:
        return 0, 0, 0
    return best_n, best_margin, best_spacing


def combine_pdf(pdfs: list[Path]):
    pdf_output = Pdf.new()
    for pdf in [Pdf.open(file) for file in pdfs]:
        for page in pdf.pages:
            pdf_output.pages.append(page)
        pdf.close()

    pdf_file = pdfs[0].parent / '.cardlatex.pdf'
    pdf_output.save(pdf_file)
    return pdf_file


# noinspection PyUnboundLocalVariable
def grid_pdf(paper_: str, file: Path, has_back: bool = False):
    if not file.exists():
        raise FileNotFoundError(f'input pdf not found: {file}')

    pdf = Pdf.open(file)
    pages: List[Page] = list(pdf.pages)

    if len({Rectangle(p.mediabox) for p in pages}) > 1:
        raise NotImplementedError('Cannot handle more than one card size.')

    paper_sizes = {
        'a4': A4,
        'a3': A3
    }
    papers = {
        **{_: [_] for _ in paper_sizes.keys()},
        'auto': ['a4', 'a3']
    }[paper_.lower()]
    papers = [paper_sizes[_] for _ in papers]

    box = Rectangle(pages[0].mediabox)
    x_n, y_n = 0, 0
    x_box, y_box = box.width, box.height
    for paper in papers:
        fit_x = find_fit(paper.width, box.width)
        fit_y = find_fit(paper.height, box.height)
        fit_x_90 = find_fit(paper.width, box.height)
        fit_y_90 = find_fit(paper.height, box.width)

        if fit_x_90[0] * fit_y_90[0] > fit_x[0] * fit_y[0]:  # if true, x_n > 0 and y_n > 0
            x_n, x_margin, x_spacing = fit_x_90
            y_n, y_margin, y_spacing = fit_y_90
            [p.rotate(90, True) for p in pages]
            x_box, y_box = box.height, box.width
            break
        else:
            if fit_x[0] * fit_y[0] > 0:
                x_n, x_margin, x_spacing = fit_x
                y_n, y_margin, y_spacing = fit_y
                break

    if x_n == 0 or y_n == 0:
        rect_str = lambda a: ', '.join(f'{round(unit_to_cm(_), 2)}' for _ in a)
        raise ValueError(f'Bounding box ({rect_str(box.upper_right)} cm) does not fit on largest available paper ({rect_str(papers[-1].upper_right)} cm)')

    grid = x_n * y_n
    front, back = [[]], [[]]
    sheets = []
    for pp in range(len(pages)):
        item = back if pp % 2 == 1 and has_back else front
        if len(item[-1]) >= grid:
            sheets.append(item[-1])
            item.append([])
        item[-1].append(pp)
        pp += 1
    sheets.extend([f_b for f_b in [front[-1], back[-1]] if f_b])

    pdf_output = Pdf.new()

    for sheet in sheets:
        x = x_margin + (0 if x_n > 1 else x_spacing)
        y = paper.height - y_margin + (0 if y_n > 1 else y_spacing)
        new_page = pdf_output.add_blank_page(page_size=(paper.width, paper.height))
        for i, p in enumerate(sheet, start=1):
            rect = Rectangle(x, y, x + x_box, y - y_box)
            new_page.add_overlay(pages[p], rect, push_stack=True, shrink=False, expand=False)
            x += x_spacing + x_box
            if i % x_n == 0:
                x = x_margin + (0 if x_n > 1 else x_spacing)
                y -= y_box + y_spacing

    logging.info(f'{file.name} as print completed! ({len(pdf.pages)} pages)')
    pdf.close()
    pdf_output.save(file)
