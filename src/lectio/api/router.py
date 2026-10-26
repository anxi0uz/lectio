from fastapi import APIRouter

from lectio.modules.courses.router import router as cr
from lectio.modules.lectures.router import router as lr
from lectio.modules.qa.router import router as qr
from lectio.modules.search.router import router as sr
from lectio.modules.summaries.router import router as smr
from lectio.modules.transcripts.router import router as tr

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(cr)
api_router.include_router(lr)
api_router.include_router(tr)
api_router.include_router(smr)
api_router.include_router(sr)
api_router.include_router(qr)
