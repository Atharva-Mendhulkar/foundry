import asyncio
import os
import sys

# Add parent to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.neo4j import neo4j_db

async def init_neo4j():
    neo4j_db.connect()
    session = await neo4j_db.get_session()
    try:
        # Constraints
        await session.run("CREATE CONSTRAINT equipment_id_unique IF NOT EXISTS FOR (e:Equipment) REQUIRE e.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT component_id_unique IF NOT EXISTS FOR (c:Component) REQUIRE c.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT failure_id_unique IF NOT EXISTS FOR (f:Failure) REQUIRE f.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT procedure_id_unique IF NOT EXISTS FOR (p:Procedure) REQUIRE p.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT workorder_id_unique IF NOT EXISTS FOR (w:WorkOrder) REQUIRE w.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT observation_id_unique IF NOT EXISTS FOR (o:Observation) REQUIRE o.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT technician_id_unique IF NOT EXISTS FOR (t:Technician) REQUIRE t.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT location_id_unique IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT shift_id_unique IF NOT EXISTS FOR (s:Shift) REQUIRE s.id IS UNIQUE")
        await session.run("CREATE CONSTRAINT riskevent_id_unique IF NOT EXISTS FOR (r:RiskEvent) REQUIRE r.id IS UNIQUE")
        
        # Indexes
        await session.run("CREATE INDEX equipment_name IF NOT EXISTS FOR (e:Equipment) ON (e.name)")
        await session.run("CREATE INDEX equipment_type IF NOT EXISTS FOR (e:Equipment) ON (e.type)")
        await session.run("CREATE INDEX component_type IF NOT EXISTS FOR (c:Component) ON (c.type)")
        await session.run("CREATE INDEX failure_mode IF NOT EXISTS FOR (f:Failure) ON (f.failure_mode)")
        await session.run("CREATE INDEX failure_timestamp IF NOT EXISTS FOR (f:Failure) ON (f.timestamp)")
        await session.run("CREATE INDEX procedure_code IF NOT EXISTS FOR (p:Procedure) ON (p.code)")
        await session.run("CREATE INDEX wo_number IF NOT EXISTS FOR (w:WorkOrder) ON (w.wo_number)")
        await session.run("CREATE INDEX wo_status IF NOT EXISTS FOR (w:WorkOrder) ON (w.status)")
        await session.run("CREATE INDEX obs_timestamp IF NOT EXISTS FOR (o:Observation) ON (o.timestamp)")
        await session.run("CREATE INDEX obs_type IF NOT EXISTS FOR (o:Observation) ON (o.obs_type)")
        await session.run("CREATE INDEX location_zone IF NOT EXISTS FOR (l:Location) ON (l.zone)")
        await session.run("CREATE INDEX shift_start IF NOT EXISTS FOR (s:Shift) ON (s.start_time)")
        await session.run("CREATE INDEX re_type IF NOT EXISTS FOR (r:RiskEvent) ON (r.event_type)")
        await session.run("CREATE INDEX re_timestamp IF NOT EXISTS FOR (r:RiskEvent) ON (r.timestamp)")
        
        # Facility Node
        await session.run("""
            MERGE (f:Facility {id: "nexus-01"})
            ON CREATE SET f.name = "Nexus Heavy Industries — Line 4"
        """)
        
        print("Neo4j initialized successfully.")
    except Exception as e:
        print(f"Error initializing Neo4j: {e}")
    finally:
        await session.close()
        await neo4j_db.close()

if __name__ == "__main__":
    asyncio.run(init_neo4j())
