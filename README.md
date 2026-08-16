# AI-SCB Year and Regions

## Data source: `county_coordinates.csv`

`county_coordinates.csv` holds one representative point per Swedish county
(SCB län code `01`–`25`): the city-centre coordinates of that county's
administrative capital (*residensstad*), not a computed geometric centroid
of the county's area. It's meant for map markers/labels, not survey-grade
geodata.

- **County codes and names, and the county → administrative-capital
  mapping**: [Statistics Sweden (SCB), Counties and municipalities in
  Sweden](https://www.scb.se/en/finding-statistics/regional-statistics-and-maps/regional-divisions/counties-and-municipalities/),
  cross-checked against [Wikipedia, "Counties of
  Sweden"](https://en.wikipedia.org/wiki/Counties_of_Sweden) (revision of
  29 May 2026). Swedish counties and their capitals are stable
  administrative facts and haven't changed since Skåne, Halland, and
  Gotland's most recent reorganisations decades ago.
- **Coordinates**: compiled from commonly published city-centre
  coordinates for each capital (e.g. as listed on each city's Wikipedia
  page or a geocoding reference such as
  [geodatos.net](https://www.geodatos.net/en/coordinates/sweden)), spot-checked
  against those sources in August 2026. They were not pulled from a single
  authoritative geodata product — if you need survey-grade centroids,
  replace this file with an export from an official source such as
  [Lantmäteriet](https://www.lantmateriet.se/) (Sweden's national mapping,
  cadastral, and land registration authority).

Compiled: August 2026.