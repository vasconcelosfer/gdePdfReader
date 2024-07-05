import pymupdf
import re
from typing import Union
from datetime import datetime
from base64 import b64decode


class GdePdfReader:

    _GDE_METADATA_DATE = 'modDate'

    _GDE_SIGNER_TITLE = 'Digitally signed by '
    _GDE_SIGNER_PATTERN = r'^Digitally signed by ([A-ZÁÉÍÓÚÜÑ]+)\s([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]*)\s([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]*)(?:\s.*)?'

    _GDE_NUMBER_TITLE = 'Número:'

    _GDE_REFERENCE_TITLE = 'Referencia: '

    _UPPER_LEFT_Y_INDEX = 1
    _BOTTOM_RIGHT_Y_INDEX = 3
    _TEXT_INDEX = 4

    _NUMBER_BIAS = 2

    def __init__(self, stream64):
        self._document = pymupdf.open(filename='pdf', stream=b64decode(stream64))
        self._is_signed = True if self._document.get_sigflags() != 0 else False
        self._gde_number = self._get_text_value(self._GDE_NUMBER_TITLE)
        self._reference = self._get_gde_reference()
        self._signer = self._get_signer_name()
        self._gde_parsed_number = GdeNumberParser(self._gde_number) if self._gde_number else None

    def _get_signer_name(self) -> Union[dict, None]:
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

    def _get_text_value(self, label, page=0):
        text_page_1 = self._document[page].get_textpage()
        search_results = text_page_1.search(label, quads=False)
        if not search_results:
            return None

        # Get the first result
        y0 = search_results[0][self._UPPER_LEFT_Y_INDEX]
        y1 = search_results[0][self._BOTTOM_RIGHT_Y_INDEX]
        first_match = True
        gde_number = None
        for block in text_page_1.extractBLOCKS():
            y0_diff = abs(y0 - block[self._UPPER_LEFT_Y_INDEX])
            y1_diff = abs(y1 - block[self._BOTTOM_RIGHT_Y_INDEX])
            if y0_diff < self._NUMBER_BIAS and y1_diff < self._NUMBER_BIAS:
                # This is because first time we gonna match with gde_number_title
                if first_match:
                    first_match = False
                    continue
                gde_number = block[self._TEXT_INDEX]
                gde_number = gde_number.replace("\n", "")
                break

        return gde_number

    def _get_gde_reference(self):
        # We now is in the first page
        last_text_page = self._document[0].get_textpage()
        for block in last_text_page.extractBLOCKS():
            if self._GDE_REFERENCE_TITLE in block[self._TEXT_INDEX]:
                reference = block[self._TEXT_INDEX].replace(self._GDE_REFERENCE_TITLE, "")
                return reference
        return None

    @property
    def gde_number(self):
        return self._gde_number

    @property
    def gde_parsed_number(self):
        return self._gde_parsed_number

    @property
    def gde_release_date(self):
        gde_date = None
        metadata = self._document.metadata
        raw_date = metadata.get(self._GDE_METADATA_DATE, '')
        # Create pattern to match with pdf date specification
        pattern = r"D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})"
        match = re.match(pattern, raw_date)

        if match:
            year, month, day, hour, minute, second = match.groups()
            # Crear un objeto datetime
            gde_date = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
        return gde_date

    @property
    def page_count(self):
        return self._document.page_count

    @property
    def is_signed(self):
        return self._is_signed

    @property
    def filename(self):
        if not self._gde_number:
            return None
        return self._gde_number + ".pdf"


class GdeNumberParser:

    _SEPARATOR = '-'
    _DIV_SEPARATOR = '#'

    _GDE_NUMBER_LENGTH = 5
    _SPECIAL_GDE_NUMBER_LENGTH = 6

    _ONLY_DIVISION = 6

    def __init__(self, gde_number):
        try:
            result = gde_number.split(self._SEPARATOR)
            if len(result) == self._GDE_NUMBER_LENGTH:
                self._type, self._year, self._number, self._agency, self._area = result
            elif len(result) == self._SPECIAL_GDE_NUMBER_LENGTH:
                self._type, self._year, self._number, self._e, self._agency, self._area = result

            self._division, self._direction = self._area.split(self._DIV_SEPARATOR)
        except ValueError:
            raise ValueError

        if len(self._division) != self._ONLY_DIVISION:
            self._has_section = True
            self._section = self._division[:self._ONLY_DIVISION-1]
            self._division = self._division[self._ONLY_DIVISION:]
        else:
            self._section = None
            self._has_section = False

    @property
    def type(self):
        return self._type

    @property
    def number(self):
        return self._number

    @property
    def year(self):
        return self._year

    @property
    def agency(self):
        return self._agency

    @property
    def section(self):
        return self._section

    @property
    def has_section(self):
        return self._has_section

    @property
    def division(self):
        return self._division

    @property
    def direction(self):
        return self._direction

    def get_abbreviation_department(self):
        if self.has_section:
            return self._section + " " + self.division[:2] + " " + self.division[2:]
        else:
            return self.division[:2] + " " + self.division[2:]


class GdeReferenceParser:

    _sigea_pattern = r"\b\d{5}-\d{1,2}-\d{4}\b"
    _sita_pattern = r"\b\d{5}SITA\d{6}[A-Z]?\b"

    _archive_pattern = f"({_sita_pattern}|{_sita_pattern})"

    def __init__(self, reference):
        # Check for archive number
        expedient = re.findall(self._archive_pattern, reference)
        self._expedient_number = expedient if expedient else None

    @property
    def expedient(self):
        return self._expedient_number
