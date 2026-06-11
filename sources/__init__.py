from .accupass import AccupassScraper
from .kkday import KKdayScraper
from .epochtimes import EpochTimesScraper
from .taichung_culture import TaichungCultureScraper

ALL_SCRAPERS = [
    AccupassScraper,
    KKdayScraper,
    EpochTimesScraper,
    TaichungCultureScraper,
]
