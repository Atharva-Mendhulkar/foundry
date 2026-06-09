import asyncio
import os
import sys
import uuid
import hashlib
from datetime import datetime, timedelta

# Add parent to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, text
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.orm.user import User, Facility
from app.db.neo4j import neo4j_db

async def seed_postgres():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        # Check if facility exists
        stmt = select(Facility).where(Facility.id == "00000000-0000-0000-0000-000000000001")
        result = await session.execute(stmt)
        facility = result.scalar_one_or_none()
        
        if not facility:
            facility = Facility(
                id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                name="Nexus Heavy Industries — Line 4",
                type="manufacturing",
                timezone="UTC"
            )
            session.add(facility)
            await session.commit()
            print("Seeded facility in Postgres.")

        # Check if user exists
        stmt = select(User).where(User.username == "engineer@nexus.com")
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                username="engineer@nexus.com",
                email="engineer@nexus.com",
                password_hash=get_password_hash("demo1234"),
                role="engineer",
                facility_id=facility.id,
                is_active=True
            )
            session.add(user)
            await session.commit()
            print("Seeded engineer@nexus.com in Postgres.")
            
    await engine.dispose()

def resolve_entity_id(entity_type: str, name: str, facility_id: str) -> str:
    canonical = f"{entity_type}:{name.lower().strip()}:{facility_id}"
    return str(uuid.UUID(bytes=hashlib.sha256(canonical.encode()).digest()[:16]))

async def seed_neo4j():
    neo4j_db.connect()
    session = await neo4j_db.get_session()
    facility_id = "nexus-01"
    
    try:
        # Create Facility
        await session.run("MERGE (f:Facility {id: $fid}) ON CREATE SET f.name='Nexus Heavy Industries — Line 4'", fid=facility_id)
        
        # 10 Equipment nodes
        equipment_list = [
            {"name": "Pump-7", "type": "centrifugal_pump", "criticality": "high", "zone": "Area A"},
            {"name": "Pump-4", "type": "centrifugal_pump", "criticality": "high", "zone": "Area A"},
            {"name": "Pump-9", "type": "centrifugal_pump", "criticality": "medium", "zone": "Area A"},
            {"name": "Compressor-3", "type": "compressor", "criticality": "high", "zone": "Area B"},
            {"name": "Compressor-1", "type": "compressor", "criticality": "low", "zone": "Area B"},
            {"name": "Hydraulic Press-2", "type": "hydraulic_press", "criticality": "critical", "zone": "Area C"},
            {"name": "Hydraulic Press-5", "type": "hydraulic_press", "criticality": "critical", "zone": "Area C"},
            {"name": "Conveyor-Belt-A", "type": "conveyor", "criticality": "medium", "zone": "Area D"},
            {"name": "Conveyor-Belt-B", "type": "conveyor", "criticality": "medium", "zone": "Area D"},
            {"name": "Cooling-Tower-1", "type": "cooling_tower", "criticality": "high", "zone": "Area E"},
        ]
        
        for eq in equipment_list:
            eq_id = resolve_entity_id("equipment", eq["name"], facility_id)
            await session.run("""
                MERGE (e:Equipment {id: $id})
                ON CREATE SET e.name=$name, e.type=$type, e.criticality=$criticality, e.facility_id=$fid, e.status='operational'
            """, id=eq_id, name=eq["name"], type=eq["type"], criticality=eq["criticality"], fid=facility_id)
            
            # Location
            loc_id = resolve_entity_id("location", eq["zone"], facility_id)
            await session.run("""
                MERGE (l:Location {id: $loc_id})
                ON CREATE SET l.zone=$zone
                WITH l
                MATCH (e:Equipment {id: $eq_id})
                MERGE (e)-[:LOCATED_AT]->(l)
            """, loc_id=loc_id, zone=eq["zone"], eq_id=eq_id)
            
        print("Seeded 10 equipment nodes + locations in Neo4j.")
        
        # 2 Procedures
        procedures = [
            {"code": "SOP-H14", "title": "Hydraulic Pressure Loss Resolution", "type": "sop"},
            {"code": "SOP-C02", "title": "Compressor Overheating Maintenance", "type": "maintenance"},
        ]
        for p in procedures:
            p_id = resolve_entity_id("procedure", p["code"], facility_id)
            await session.run("""
                MERGE (pr:Procedure {id: $id})
                ON CREATE SET pr.code=$code, pr.title=$title, pr.type=$type
            """, id=p_id, code=p["code"], title=p["title"], type=p["type"])
            
        print("Seeded 2 procedures in Neo4j.")
            
        # 5 Failures
        now = datetime.utcnow()
        failures = [
            {"eq": "Pump-7", "desc": "Loss of pressure due to seal leak", "mode": "pressure_loss", "sev": "high", "proc": "SOP-H14", "days_ago": 5},
            {"eq": "Pump-4", "desc": "Vibration leading to pressure drop", "mode": "pressure_loss", "sev": "medium", "proc": "SOP-H14", "days_ago": 15},
            {"eq": "Pump-7", "desc": "Seal rupture causing pressure loss", "mode": "pressure_loss", "sev": "high", "proc": "SOP-H14", "days_ago": 25},
            {"eq": "Compressor-3", "desc": "Overheating shut down", "mode": "overheating", "sev": "high", "proc": "SOP-C02", "days_ago": 10},
            {"eq": "Hydraulic Press-2", "desc": "Hydraulic fluid leak", "mode": "fluid_leak", "sev": "critical", "proc": None, "days_ago": 2},
        ]
        
        for i, f in enumerate(failures):
            eq_id = resolve_entity_id("equipment", f["eq"], facility_id)
            f_id = resolve_entity_id("failure", f"fail_{i}_{f['eq']}", facility_id)
            f_time = (now - timedelta(days=f["days_ago"])).isoformat()
            
            await session.run("""
                MERGE (fail:Failure {id: $f_id})
                ON CREATE SET fail.description=$desc, fail.failure_mode=$mode, fail.severity=$sev, fail.timestamp=datetime($time), fail.resolved=true
                WITH fail
                MATCH (e:Equipment {id: $eq_id})
                MERGE (e)-[:EXPERIENCED {at: datetime($time), count: 1}]->(fail)
            """, f_id=f_id, desc=f["desc"], mode=f["mode"], sev=f["sev"], time=f_time, eq_id=eq_id)
            
            if f["proc"]:
                p_id = resolve_entity_id("procedure", f["proc"], facility_id)
                await session.run("""
                    MATCH (fail:Failure {id: $f_id})
                    MATCH (p:Procedure {id: $p_id})
                    MERGE (fail)-[:RESOLVED_BY {success: true}]->(p)
                """, f_id=f_id, p_id=p_id)
                
        print("Seeded 5 failures in Neo4j.")

    except Exception as e:
        print(f"Error seeding Neo4j: {e}")
    finally:
        await session.close()
        await neo4j_db.close()

if __name__ == "__main__":
    asyncio.run(seed_postgres())
    asyncio.run(seed_neo4j())
