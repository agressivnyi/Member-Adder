from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data.config import base_settings_for_create
from utils.db.models import Base

db_url = f"{base_settings_for_create}"
engine = create_engine(db_url, echo=False, future=True)
Session = sessionmaker(bind=engine)


def create_tables():
    session = Session()
    Base.metadata.create_all(engine)
    session.close()


if __name__ == "__main__":
    create_tables()
    print('Таблицы успешно созданы.')
