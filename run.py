import os

import uvicorn

if __name__ == "__main__":
    host = "127.0.0.1" if os.getenv("PYRIGHT") else "0.0.0.0"
    port = int(os.getenv("WEB_PORT", "8130"))

    conf = uvicorn.Config("pyright-api:app", host=host, port=port, workers=5, proxy_headers=True, forwarded_allow_ips="*")
    server = uvicorn.Server(conf)

    server.run()
