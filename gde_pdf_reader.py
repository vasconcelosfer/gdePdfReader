import pymupdf
import re
from typing import Union
from datetime import datetime


class GdePdfReader:

    _GDE_METADATA_DATE = 'modDate'

    _GDE_SIGNER_TITLE = 'Digitally signed by '
    _GDE_SIGNER_PATTERN = r'^Digitally signed by ([A-ZÁÉÍÓÚÜÑ]+)\s([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]*)\s([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]*)(?:\s.*)?'

    _GDE_NUMBER_TITLE = 'Número:'

    _UPPER_LEFT_Y_INDEX = 1
    _BOTTOM_RIGHT_Y_INDEX = 3
    _TEXT_INDEX = 4

    _NUMBER_BIAS = 2

    def __init__(self, filename):
        self._document = pymupdf.open(filename=filename)
        self._is_signed = True if self._document.get_sigflags() != 0 else False

    @property
    def page_count(self):
        return self._document.page_count

    @property
    def is_signed(self):
        return self._is_signed

    def get_signer_name(self) -> Union[dict, None]:
        result = None
        if not self.is_signed:
            return None
        last_text_page = self._document[-1].get_textpage()
        for block in last_text_page.extractBLOCKS():
            # Check if block has Digitally signed
            if self._GDE_SIGNER_TITLE in block[self._TEXT_INDEX]:
                result = block[self._TEXT_INDEX]
                # As we know that the document has two block that start with Digitally Signed we get the first
                break
        # We know the pattern of signer name: SURNAME, Firstname Second name
        # Create pattern to match with pdf date specification
        pattern = self._GDE_SIGNER_PATTERN
        match = re.match(pattern, result, re.DOTALL)
        if not match:
            return None

        signer_name = dict()
        signer_name['surname'] = match.group(1)
        signer_name['name'] = match.group(2)
        signer_name['second_name'] = match.group(3) if match.group(3) else None
        return signer_name

    def get_gde_number(self):
        gde_number = None
        # Get y coordinates, search for GDE Number Title.
        # We know is it in first page

        text_page_1 = self._document[0].get_textpage()
        search_results = text_page_1.search(self._GDE_NUMBER_TITLE, quads=False)
        if not search_results:
            return gde_number

        # Get the first result
        y0 = search_results[0][self._UPPER_LEFT_Y_INDEX]
        y1 = search_results[0][self._BOTTOM_RIGHT_Y_INDEX]
        first_match = True
        for block in text_page_1.extractBLOCKS():
            y0_diff = abs(y0 - block[self._UPPER_LEFT_Y_INDEX])
            y1_diff = abs(y1 - block[self._BOTTOM_RIGHT_Y_INDEX])
            if y0_diff < self._NUMBER_BIAS and y1_diff < self._NUMBER_BIAS:
                # This is because first time we gonna mathc with gde_number_title
                if first_match:
                    first_match = False
                    continue
                gde_number = block[self._TEXT_INDEX]
                gde_number = gde_number.replace("\n", "")
                break

        return gde_number

    def get_gde_date(self):
        gde_date = None
        metadata = self._document.metadata
        raw_date = metadata.get(self._GDE_METADATA_DATE, '')
        # Create pattern to match with pdf date specification
        pattern = r"D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})"
        match = re.match(pattern, raw_date)

        if match:
            year, month, day, hour, minute, second = match.groups()
            # Crear un objeto datetime
            gde_date = datetime(int(year), int(month), int(day), int(hour), int(minute),int(second))
        return gde_date

