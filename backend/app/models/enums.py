from enum import Enum


class RunStatus(str, Enum):
    PENDING   = "pending"
    CRAWLING  = "crawling"
    ANALYZING = "analyzing"
    JUDGING   = "judging"
    COMPLETE  = "complete"
    FAILED    = "failed"


class CrawlStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED  = "failed"
