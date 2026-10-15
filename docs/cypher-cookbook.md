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
Match without an arrow, then use `startNode()` to read the arrays the right way round.
```cypher
MATCH (h:Driver {driver_id: 'hamilton'})-[t:TEAMMATE_OF]-(mate)
WITH h, t, mate, startNode(t) = h AS h_first
RETURN mate.name AS teammate,
       CASE WHEN h_first THEN t.quali_h2h ELSE reverse(t.quali_h2h) END AS quali_h2h,
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
