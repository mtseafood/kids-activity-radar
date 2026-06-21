from .accupass import AccupassScraper
from .kkday import KKdayScraper
from .epochtimes import EpochTimesScraper
from .taichung_culture import TaichungCultureScraper
from .culture_cloud import CultureCloudScraper
from .niceday import NicedayScraper
from .brands import BrandExperienceScraper
from .pinkoi import PinkoiScraper
from .beclass import BeClassScraper

ALL_SCRAPERS = [
    BrandExperienceScraper,
    NicedayScraper,
    PinkoiScraper,
    BeClassScraper,
    AccupassScraper,
    KKdayScraper,
    EpochTimesScraper,
    TaichungCultureScraper,
    CultureCloudScraper,
]
