import os, json, secrets, hashlib, hmac, time, uuid
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

BASE=Path(__file__).resolve().parent.parent
DATA=Path(os.getenv('DATA_DIR', str(BASE/'data'))); DATA.mkdir(parents=True,exist_ok=True)
DB=os.getenv('DATABASE_URL',f'sqlite:///{DATA}/office.db')
if DB.startswith('postgres://'): DB='postgresql://'+DB[len('postgres://'):]
engine=create_engine(DB,pool_pre_ping=True,connect_args={'check_same_thread':False} if DB.startswith('sqlite') else {})
Session=sessionmaker(bind=engine)
Base=declarative_base()
class Record(Base):
    __tablename__='records'
    id=Column(Integer,primary_key=True)
    kind=Column(String(40),nullable=False,index=True)
    public_id=Column(String(120),nullable=False)
    payload=Column(Text,nullable=False)
    updated_at=Column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    __table_args__=(UniqueConstraint('kind','public_id'),)
class Asset(Base):
    __tablename__='assets'
    id=Column(String(36),primary_key=True)
    task_id=Column(String(120),nullable=False,index=True)
    stage=Column(String(30),nullable=False)
    filename=Column(String(255),nullable=False)
    content_type=Column(String(150))
    size=Column(Integer,nullable=False)
    stored_name=Column(String(100),nullable=False)
Base.metadata.create_all(engine)
app=FastAPI(title='AI Private Office API',version='1.0.0',docs_url='/api/docs',openapi_url='/api/openapi.json')
secret=os.getenv('SESSION_SECRET','')
password=os.getenv('CEO_PASSWORD','')
if not secret or not password:
    raise RuntimeError('Set SESSION_SECRET and CEO_PASSWORD environment variables before starting')
signer=URLSafeTimedSerializer(secret,salt='office-ceo-v1')
class Login(BaseModel): password:str
class Snapshot(BaseModel):
    staff:list[dict]=Field(default_factory=list)
    tasks:list[dict]=Field(default_factory=list)
    activity:list[dict]=Field(default_factory=list)
    intelligence:dict[str,list[dict]]=Field(default_factory=dict)

def auth(request:Request):
    token=request.headers.get('authorization','')
    if not token.startswith('Bearer '):raise HTTPException(401,'Login required')
    try:
        val=signer.loads(token[7:],max_age=60*60*24)
        if val!='ceo':raise ValueError()
    except (BadSignature,SignatureExpired,ValueError):raise HTTPException(401,'Session expired; login again')
    return True
@app.post('/api/login')
def login(data:Login):
    if not hmac.compare_digest(data.password,password):raise HTTPException(401,'Incorrect password')
    return {'token':signer.dumps('ceo'),'expires_in':86400}
@app.get('/api/health')
def health():return {'status':'ok'}
KINDS=('staff','tasks','activity','news','planning','analysis','ideas')
@app.get('/api/snapshot')
def get_snapshot(_=Depends(auth)):
    result={'staff':[],'tasks':[],'activity':[],'intelligence':{k:[] for k in KINDS[3:]}}
    with Session() as db:
        for r in db.query(Record).all():
            item=json.loads(r.payload)
            if r.kind in KINDS[3:]:result['intelligence'][r.kind].append(item)
            elif r.kind in result:result[r.kind].append(item)
    return result
@app.put('/api/snapshot')
def put_snapshot(data:Snapshot,_=Depends(auth)):
    # Single CEO workspace: transactional replacement. Do not expose this endpoint to untrusted users.
    incoming={'staff':data.staff,'tasks':data.tasks,'activity':data.activity[:60]}
    incoming.update({k:data.intelligence.get(k,[]) for k in KINDS[3:]})
    if sum(map(len,incoming.values()))>10000:raise HTTPException(413,'Too many records')
    with Session.begin() as db:
        for kind,items in incoming.items():
            db.query(Record).filter(Record.kind==kind).delete()
            for index,item in enumerate(items):
                if len(json.dumps(item))>200000:raise HTTPException(413,'Record too large')
                ident=str(item.get('id',index)) if kind not in ('activity',) else str(index)
                db.add(Record(kind=kind,public_id=ident,payload=json.dumps(item,ensure_ascii=False)))
    return {'ok':True}
ASSET_DIR=DATA/'uploads';ASSET_DIR.mkdir(exist_ok=True)
MAX_BYTES=int(os.getenv('MAX_UPLOAD_MB','25'))*1024*1024
ALLOWED={'.pdf','.txt','.csv','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.png','.jpg','.jpeg','.gif','.webp','.mp4','.mov','.webm'}
@app.post('/api/tasks/{task_id}/files')
async def upload_file(task_id:str,stage:str='instruction',file:UploadFile=File(...),_=Depends(auth)):
    if stage not in ('instruction','draft','final'):raise HTTPException(400,'Invalid stage')
    if len(task_id)>120:raise HTTPException(400,'Invalid task ID')
    filename=Path(file.filename or 'upload').name[:255]
    ext=Path(filename).suffix.lower()
    if ext not in ALLOWED:raise HTTPException(415,'File type not allowed')
    ident=str(uuid.uuid4());stored=ident+ext;path=ASSET_DIR/stored;size=0
    try:
        with path.open('wb') as out:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>MAX_BYTES:raise HTTPException(413,'File too large')
                out.write(chunk)
        with Session.begin() as db:
            db.add(Asset(id=ident,task_id=task_id,stage=stage,filename=filename,content_type=file.content_type,size=size,stored_name=stored))
    except Exception:
        path.unlink(missing_ok=True);raise
    return {'id':ident,'filename':filename,'stage':stage,'size':size}
@app.get('/api/tasks/{task_id}/files')
def list_files(task_id:str,_=Depends(auth)):
    with Session() as db:
        return [{'id':a.id,'filename':a.filename,'stage':a.stage,'size':a.size} for a in db.query(Asset).filter_by(task_id=task_id).all()]
@app.get('/api/files/{asset_id}')
def get_file(asset_id:str,_=Depends(auth)):
    with Session() as db:
        a=db.get(Asset,asset_id)
        if not a:raise HTTPException(404,'File not found')
        path=ASSET_DIR/a.stored_name
        if not path.exists():raise HTTPException(404,'Stored file missing')
        return FileResponse(path,filename=a.filename,media_type='application/octet-stream')

# AI task execution: draft generation only; no external actions or autonomous approvals.
from openai import AsyncOpenAI
from fastapi import status
from sqlalchemy import select
from pydantic import field_validator
class AgentRun(BaseModel):
    task_id: str = Field(min_length=1,max_length=120)
    title: str = Field(min_length=1,max_length=200)
    instruction: str = Field(min_length=1,max_length=12000)
    staff_name: str = Field(min_length=1,max_length=120)
    staff_role: str = Field(min_length=1,max_length=160)
    staff_description: str = Field(default='',max_length=3000)
    @field_validator('instruction')
    @classmethod
    def valid_instruction(cls,v):
        if not v.strip(): raise ValueError('Instruction required')
        return v
@app.post('/api/engine/draft')
async def generate_draft(data:AgentRun,_=Depends(auth)):
    if not os.getenv('OPENAI_API_KEY'):
        raise HTTPException(503,'OPENAI_API_KEY not configured')
    model=os.getenv('OPENAI_MODEL','gpt-4.1-mini')
    client=AsyncOpenAI(api_key=os.environ['OPENAI_API_KEY'],timeout=75,max_retries=1)
    try:
        response=await client.responses.create(
            model=model,
            instructions=('You are an AI office staff member. Your name: '+data.staff_name+'; role: '+data.staff_role+'. Job description: '+data.staff_description+'. Produce a professional, useful draft for CEO review. Never claim to have accessed websites, private systems, files or apps. Do not perform external actions. Clearly label unverified claims and assumptions.'),
            input='Task: '+data.title+'\nCEO instruction: '+data.instruction,
            max_output_tokens=2200,
            store=False
        )
    except Exception:
        # Avoid exposing provider errors or credentials to the browser.
        raise HTTPException(502,'AI provider request failed; check server logs and provider configuration')
    result=(response.output_text or '').strip()
    if not result: raise HTTPException(502,'AI returned no draft')
    # Draft is returned to the CEO; the browser must explicitly save it.
    return {'task_id':data.task_id,'draft':result,'model':model,'status':'draft_only'}

@app.get('/api')
def api_root():return {'service':'AI Private Office','docs':'/api/docs'}
app.mount('/',StaticFiles(directory=str(BASE/'frontend'),html=True),name='frontend')
