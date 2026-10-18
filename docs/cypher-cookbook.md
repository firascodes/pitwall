# Cypher cookbook

Queries to paste into the Neo4j Browser (http://localhost:7474). Each one shows a graph idea from the [architecture plan](architecture.md).

## See the shape of the graph
```cypher
CALL db.schema.visualization()
```

## One race weekend as a picture
```cypher
MATCH (r:Race {race_id: '2026-17'})-[:HAS_SESSION]->(s:Session)<-[:IN_SESSION]-(res:Result)<-[:ACHIEVED]-(d:Driver)
WHERE s.type = 'Q' AND res.position <= 5
MATCH (res)-[:FOR_TEAM]->(t:Constructor)
RETURN r, s, res, d, t
```

## Drivers who changed team mid-season (stints)
```cypher
MATCH (d:Driver)-[:HAS_STINT]->(st:Stint)-[:FOR_TEAM]->(t:Constructor)
WITH d, collect(t.name + ' R' + st.from_round + '-' + st.to_round) AS stints
WHERE size(stints) > 1
RETURN d.name AS driver, stints
```

## Every teammate battle
`TEAMMATE_OF` is stored once per pair, from the lower `driver_id` to the higher. Index 0 of each array is the first driver. A negative `avg_quali_gap_pct` means the first driver was faster.
```cypher
MATCH (a:Driver)-[t:TEAMMATE_OF]->(b:Driver)
RETURN t.team AS team, a.code + ' vs ' + b.code AS pair,
       t.quali_h2h AS quali, t.race_h2h AS race, t.avg_quali_gap_pct AS gap_pct_of_first
ORDER BY team
```

## One driver's head-to-head, from their own side
Match without an arrow, then use `startNode()` to read the arrays the right way round. Swap the pair by index: list properties are stored as typed arrays (`long[]`), and `reverse()` rejects them.
```cypher
MATCH (h:Driver {driver_id: 'hamilton'})-[t:TEAMMATE_OF]-(mate)
WITH h, t, mate, startNode(t) = h AS h_first
RETURN mate.name AS teammate,
       CASE WHEN h_first THEN t.quali_h2h ELSE [t.quali_h2h[1], t.quali_h2h[0]] END AS quali_h2h,
       CASE WHEN h_first THEN t.avg_quali_gap_pct ELSE -t.avg_quali_gap_pct END AS gap_pct
```

## Who was faster than their teammate at each circuit?
```cypher
MATCH (d:Driver {driver_id: 'hamilton'})-[:ACHIEVED]->(res:Result)-[:IN_SESSION]->(:Session {type: 'Q'})
      <-[:HAS_SESSION]-(r:Race)-[:AT]->(c:Circuit)
WHERE res.gap_to_teammate_pct IS NOT NULL
RETURN r.round AS round, c.name AS circuit, res.gap_to_teammate_pct AS gap_pct
ORDER BY gap_pct
```

## Laps

### Deleted laps in a session, with the reason
Bind the `Result` once and reuse the variable. Within one `MATCH`, Cypher never uses the same relationship twice (**relationship isomorphism**). Writing the `ACHIEVED` hop twice would force it to find a *different* result.
```cypher
MATCH (d:Driver)-[:ACHIEVED]->(res:Result)-[:IN_SESSION]->(:Session {session_id: '2026-17-Q'}),
      (res)-[:HAS_LAP]->(l:Lap {deleted: true})
RETURN d.code AS driver, l.part AS part, l.lap_number AS lap, l.deleted_reason AS reason
ORDER BY part, lap
```

### Who gained most between their first and last Q3 push lap?
A push lap is timed, not deleted, and not an out-lap or in-lap.
```cypher
MATCH (d:Driver)-[:ACHIEVED]->(:Result {result_id: '2026-17-Q-' + d.driver_id})-[:HAS_LAP]->(l:Lap {part: 'Q3'})
WHERE l.lap_time_ms IS NOT NULL AND NOT l.deleted AND NOT l.pit_in AND NOT l.pit_out
WITH d, l ORDER BY l.lap_number
WITH d, collect(l) AS laps WHERE size(laps) > 1
RETURN d.code AS driver, laps[0].lap_time_ms / 1000.0 AS first_run,
       laps[-1].lap_time_ms / 1000.0 AS last_run,
       round((laps[0].lap_time_ms - laps[-1].lap_time_ms) / 1000.0, 3) AS gained_s
ORDER BY gained_s DESC
```

### Fastest race lap on each tyre compound
```cypher
MATCH (d:Driver)-[:ACHIEVED]->(res:Result)-[:IN_SESSION]->(:Session {session_id: '2026-17-R'}),
      (res)-[:HAS_LAP]->(l:Lap)
WHERE l.lap_time_ms IS NOT NULL AND NOT l.pit_in AND NOT l.pit_out AND NOT l.deleted
WITH l.compound AS tyre, d, l ORDER BY l.lap_time_ms
WITH tyre, collect({driver: d.code, lap: l.lap_number, tyre_age: l.tyre_age, s: l.lap_time_ms / 1000.0})[0] AS best
RETURN tyre, best ORDER BY best.s
```
