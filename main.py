from fastapi import FastAPI
from app.routes import sessions

app = FastAPI(title='Deepwork AI')

app.include_router(sessions.router, prefix='/sessions')

@app.get('/')
def root():
    return {'message': 'Deepwork AI API running'}
