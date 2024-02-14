from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    full_name = Column(String(255), nullable=False)
    username = Column(String(255), nullable=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    last_message_id = Column(Integer, nullable=True)
    task_status = Column(Boolean, default=False)
    proxy_server = Column(String(255), nullable=True)
    proxy_port = Column(Integer, nullable=True)
    proxy_type = Column(String(255), nullable=True)
    proxy_login = Column(String(255), nullable=True)
    proxy_password = Column(String(255), nullable=True)
    proxy_ipv6 = Column(Boolean, default=False)
    device_name = Column(String(255), default='Android')
    auth_keys = relationship("AuthKey", back_populates="user")


class AuthKey(Base):
    __tablename__ = 'auth_keys'

    id = Column(Integer, primary_key=True)
    key = Column(String(255), nullable=False, unique=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id'))
    is_active = Column(Boolean, default=False)

    user = relationship("User", back_populates="auth_keys")


class Accounts(Base):
    __tablename__ = 'sessions'

    id = Column(Integer, primary_key=True)
    number = Column(String(255), nullable=False, unique=True)
    hash_value = Column(String(255), nullable=False)
    status = Column(String(255), default='free')
    restriction_time = Column(String(255), default=None)


class Blacklist(Base):
    __tablename__ = 'blacklist'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
