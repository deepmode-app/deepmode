from fastapi import APIRouter

router = APIRouter()

@router.post('/')
def create_session():
    return {'status': 'session created (placeholder)'}
