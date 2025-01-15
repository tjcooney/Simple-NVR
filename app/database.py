from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class Camera(Base):
    __tablename__ = 'cameras'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    stream_url = Column(String, nullable=False)
    username = Column(String)
    password = Column(String)

def init_db():
    engine = create_engine('sqlite:////data/cameras.db')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()