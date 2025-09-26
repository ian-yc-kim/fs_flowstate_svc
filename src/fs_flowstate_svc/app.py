from fastapi import FastAPI

from fs_flowstate_svc.api.auth_router import auth_router

app = FastAPI(debug=True)

# add routers
app.include_router(auth_router)
