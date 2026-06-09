from neo4j import AsyncGraphDatabase, AsyncDriver
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class Neo4jConnection:
    def __init__(self):
        self.driver: AsyncDriver | None = None

    def connect(self):
        try:
            self.driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            logger.info("Connected to Neo4j")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self):
        if self.driver:
            await self.driver.close()
            logger.info("Closed Neo4j connection")

    async def get_session(self):
        if not self.driver:
            self.connect()
        return self.driver.session()

neo4j_db = Neo4jConnection()

async def get_neo4j():
    session = await neo4j_db.get_session()
    try:
        yield session
    finally:
        await session.close()
