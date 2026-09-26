from sqlalchemy import Column, Integer, String
from database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)

    camera_id = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    name = Column(
        String,
        nullable=False
    )

    manufacturer = Column(
        String,
        nullable=True
    )

    protocol = Column(
        String,
        nullable=False
    )

    host = Column(
        String,
        nullable=True
    )

    port = Column(
        Integer,
        nullable=True
    )

    # Full camera stream path/URL
    stream_url = Column(
        String,
        nullable=True
    )

    username = Column(
        String,
        nullable=True
    )

    password = Column(
        String,
        nullable=True
    )