from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
import uuid

from app.config import GOOGLE_AUTH_URL, SCOPE
from app.schema import ClientOAuthConfig
from app.models import CLIENTS, TOKENS, OAUTH_STATES
from app.service.oauth_service import exchange_code_for_token
from app.service.google_api import google_get

app = FastAPI(title="GBP Reviews – Decentralized OAuth POC")


# ----------------------------
# STEP 1: Register client OAuth
# ----------------------------
@app.post("/client/register")
def register_client(config: ClientOAuthConfig):
    CLIENTS[config.client_id] = config
    return {"message": "Client registered", "client_id": config.client_id}


# ----------------------------
# STEP 2: Login (Browser only)
# ----------------------------
@app.get("/login/{client_id}")
def login(client_id: str):
    client = CLIENTS.get(client_id)
    if not client:
        return JSONResponse({"error": "Client not registered"}, 404)

    state = str(uuid.uuid4())
    OAUTH_STATES[state] = client_id

    auth_url = (
        f"{GOOGLE_AUTH_URL}"
        f"?client_id={client.client_id}"
        f"&redirect_uri={client.redirect_uri}"
        f"&response_type=code"
        f"&scope={SCOPE}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={state}"
    )
    print(f"after login : {auth_url}")
    return RedirectResponse(auth_url)


# ----------------------------
# STEP 3: OAuth callback
# ----------------------------
@app.get("/auth/callback")
async def auth_callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    client_id = OAUTH_STATES.get(state)
    if not client_id:
        return JSONResponse({"error": "Invalid OAuth state"}, 400)

    client = CLIENTS[client_id]

    token = await exchange_code_for_token(
        code=code,
        client_id=client.client_id,
        client_secret=client.client_secret,
        redirect_uri=str(client.redirect_uri),
    )

    TOKENS[client_id] = token
    del OAUTH_STATES[state]
    print(f"token : {token}")
    return {"message": "OAuth success", "next": f"/accounts/{client_id}"}


# ----------------------------
# STEP 4: Accounts
# ----------------------------
@app.get("/accounts/{client_id}")
async def get_accounts(client_id: str):
    token = TOKENS.get(client_id)
    if not token:
        return JSONResponse({"error": "Not authenticated"}, 401)

    return await google_get(
        "https://mybusinessaccountmanagement.googleapis.com/v1/accounts",
        token["access_token"],
    )

# --------------------------------------------------
# STEP 5: Locations
# --------------------------------------------------
@app.get("/accounts/{client_id}/{account_id}/locations")
async def get_locations(client_id: str, account_id: str):
    token = TOKENS.get(client_id)
    if not token:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations"
    return await google_get(url, token["access_token"])


# --------------------------------------------------
# STEP 6: Reviews (IMPORTANT FIX)
# --------------------------------------------------
@app.get("/accounts/{client_id}/{account_id}/{location_id}/reviews")
async def get_reviews(client_id: str, account_id: str, location_id: str):
    token = TOKENS.get(client_id)
    if not token:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    url = (
        f"https://mybusiness.googleapis.com/v4/"
        f"{account_id}/locations/{location_id}/reviews"
    )

    raw = await google_get(url, token["access_token"])

    reviews = []
    for r in raw.get("reviews", []):
        reviews.append({
            "review_id": r.get("reviewId"),
            "rating": r.get("starRating"),
            "comment": r.get("comment"),
            "reviewer_name": r.get("reviewer", {}).get("displayName"),
            "reviewer_email": "not_provided_by_google",
            "organization": account_id,
            "location": location_id
        })

    return {"reviews": reviews}
