# Model cards

The registry starts empty. A row is created only when something registers it. Weight files stay under gitignored `models/` and are not loaded at process startup.

Each shipped model also has a markdown card in this directory. The API card (`card_markdown` on `GET /api/models`) is generated from the database row, so the Model Laboratory does not hardcode a benchmark or a training status.

Session 6A registers no weights. The only loader key is `registry_only`, which checks a checksum when a weight path is set and does not execute the file.
