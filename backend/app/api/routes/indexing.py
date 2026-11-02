from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def indexing_status():
    """Get indexing status - placeholder."""
    return {"message": "Indexing endpoints not yet implemented"}