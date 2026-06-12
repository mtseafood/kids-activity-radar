from .accupass import AccupassScraper
from .kkday import KKdayScraper
from .epochtimes import EpochTimesScraper
from .taichung_culture import TaichungCultureScraper
from .niceday import NicedayScraper
from .brands import BrandExperienceScraper

ALL_SCRAPERS = [
    BrandExperienceScraper,
    NicedayScraper,
    AccupassScraper,
    KKdayScraper,
    EpochTimesScraper,
    TaichungCultureScraper,
]
