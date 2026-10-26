from lectio.core.exceptions import ConflictError


class SummaryNotReadyError(ConflictError):
    default_detail = "Summary can be regenerated only for a processed lecture"
