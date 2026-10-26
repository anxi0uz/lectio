from fastapi import APIRouter

from lectio.modules.auth.router import router as ar
from lectio.modules.bookmarks.router import router as br
from lectio.modules.courses.router import router as cr
from lectio.modules.dashboard.router import router as dr
from lectio.modules.enrollments.router import router as er
from lectio.modules.favorites.router import router as fr
from lectio.modules.lectures.router import router as lr
from lectio.modules.progress.router import router as pr
from lectio.modules.qa.router import router as qr
from lectio.modules.search.router import router as sr
from lectio.modules.summaries.router import router as smr
from lectio.modules.transcripts.router import router as tr
from lectio.modules.users.router import router as ur

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(ar)
api_router.include_router(ur)
api_router.include_router(cr)
api_router.include_router(er)
api_router.include_router(lr)
api_router.include_router(tr)
api_router.include_router(smr)
api_router.include_router(sr)
api_router.include_router(qr)
api_router.include_router(pr)
api_router.include_router(fr)
api_router.include_router(br)
api_router.include_router(dr)
