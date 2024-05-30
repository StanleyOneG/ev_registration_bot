import enum
from typing import Literal
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class VisitType(enum.Enum):
    THERAPY = "therapy"
    LECTURE = "lecture"


class Commune(enum.Enum):
    AMERICAN = "american_calendar_configs"
    GERMAN = "german_calendar_configs"


def get_visit_type_color(
    visit_type: VisitType,
    commune: Commune,
) -> Literal[5] | Literal[7] | Literal[1]:
    logger.info(f"visit_type: {visit_type.name}")
    if visit_type.name == VisitType.THERAPY.name:
        return 5

    if commune.name == Commune.AMERICAN.name:
        return 7

    return 1
