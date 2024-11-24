# Pyright API

First and foremost, I made this intended for private use, on a private network.

It's a quick and dirty [Litestar](https://litestar.dev/) RESTful API that runs pyright under the hood so that I don't need to include this in other services that can run my pyright code, like [Mipha](https://github.com/AbstractUmbra/Mipha/blob/68e4d20cd568c865641a5b12c5fb408c82398b58/extensions/rtfx.py#L443-L462).

To set it up, you can use the pre-built image from `ghcr.io/abstractumbra/pyright-api:latest`, like the docker compose file in this repo.
Or if you want to clone and built it yourself, you can do that too.

You just need to create a file named `api_key` and enter an API token within. Users who have this token can currently force the pyright version to update, but more functionality may be added later.

### Running locally

It will run locally, but by default will bind to `0.0.0.0:port`. You can modify this behaviour by setting an env variable before running, like so:
`PYRIGHT=1 python run.py`
