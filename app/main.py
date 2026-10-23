"""Power Desk: a small ERCOT-style power trading web app (the system under test).

Pages:  /login  /  /trades/new  /blotter  /positions
API:    /api/health  /api/login  /api/logout  /api/prices  /api/trades  /api/positions
Test-only: POST /api/test/reset (exists only when APP_ENV=test)
"""

from __future__ import annotations

import datetime as dt
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, db, pricing, trading
from .auth import User

BASE_DIR = Path(__file__).parent
APP_ENV = os.getenv("APP_ENV", "dev")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me")


def today() -> dt.date:
    """Business date. APP_TODAY pins it so test runs are reproducible."""
    override = os.getenv("APP_TODAY")
    return dt.date.fromisoformat(override) if override else dt.date.today()


def current_marks() -> dict[str, float]:
    return pricing.get_marks(today(), fixed=APP_ENV == "test")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    yield


app = FastAPI(title="Power Desk", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def usd(value: float) -> str:
    """-144.0 -> '-$144.00' (accounting style, sign before the currency symbol)."""
    return f"-${abs(value):,.2f}" if value < 0 else f"${value:,.2f}"


templates.env.filters["usd"] = usd


# ---------------------------------------------------------------- helpers


def current_user(request: Request) -> User | None:
    username = request.session.get("user")
    return auth.get_user(username) if username else None


def page_user(request: Request) -> User:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def api_user(request: Request) -> User:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def render(request: Request, name: str, status_code: int = 200, **ctx):
    context = {
        "user": current_user(request),
        "flash": request.session.pop("flash", None),
        "app_env": APP_ENV,
        "today": today(),
        **ctx,
    }
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def trade_scope(user: User) -> str | None:
    """Traders see their own book; viewers (risk, management) see the whole desk."""
    return None if user.role == "viewer" else user.username


def book_trade(user: User, data: dict, confirmed: bool) -> tuple[dict | None, list[trading.Issue]]:
    req, issues = trading.parse_trade(data)
    if issues:
        return None, issues
    issues = trading.validate_trade(
        req,
        today=today(),
        mark=current_marks().get(req.hub),
        current_net_mw=db.net_mw(user.username, req.hub),
        price_confirmed=confirmed,
    )
    if issues:
        return None, issues
    return db.insert_trade(user.username, req), []


def ticket_context(form: dict | None = None, errors=None) -> dict:
    errors = errors or []
    default = {
        "side": "BUY",
        "hub": "HB_HOUSTON",
        "product": "ON_PEAK",
        "quantity_mw": "",
        "price": "",
        "delivery_date": (today() + dt.timedelta(days=1)).isoformat(),
    }
    return {
        "form": {**default, **(form or {})},
        "errors": errors,
        "needs_confirm": any(e.code == "PRICE_CONFIRMATION_REQUIRED" for e in errors),
        "marks": current_marks(),
        "hubs": trading.HUBS,
        "products": trading.PRODUCT_HOURS,
        "min_date": (today() + dt.timedelta(days=1)).isoformat(),
        "max_date": (today() + dt.timedelta(days=trading.MAX_DAYS_FORWARD)).isoformat(),
    }


# ---------------------------------------------------------------- pages


@app.get("/login")
def login_form(request: Request):
    if current_user(request):
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html", error=None, username="")


@app.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    username = str(form.get("username", ""))
    user = auth.authenticate(username, str(form.get("password", "")))
    if user is None:
        return render(
            request,
            "login.html",
            status_code=401,
            error="Invalid username or password.",
            username=username,
        )
    request.session["user"] = user.username
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/")
def dashboard(request: Request, user: User = Depends(page_user)):
    trades = db.list_trades(trader=trade_scope(user))
    positions = trading.compute_positions(trades, current_marks())
    return render(
        request,
        "dashboard.html",
        marks=current_marks(),
        trade_count=len(trades),
        total_pnl=positions["total_pnl"],
    )


@app.get("/trades/new")
def trade_form(request: Request, user: User = Depends(page_user)):
    if not user.can_trade:
        return render(request, "forbidden.html", status_code=403)
    return render(request, "trade_new.html", **ticket_context())


@app.post("/trades/new")
async def trade_submit(request: Request, user: User = Depends(page_user)):
    if not user.can_trade:
        return render(request, "forbidden.html", status_code=403)
    form = {k: str(v) for k, v in (await request.form()).items()}
    confirmed = form.pop("confirm_price", None) == "on"
    trade, issues = book_trade(user, form, confirmed)
    if issues:
        return render(request, "trade_new.html", status_code=422, **ticket_context(form, issues))
    request.session["flash"] = (
        f"Trade #{trade['id']} booked: {trade['side']} {trade['quantity_mw']} MW "
        f"{trade['hub']} {trade['product']} @ ${trade['price']:,.2f}"
    )
    return RedirectResponse("/blotter", status_code=303)


@app.get("/blotter")
def blotter(request: Request, hub: str = "", user: User = Depends(page_user)):
    hub = hub if hub in trading.HUBS else ""
    trades = db.list_trades(trader=trade_scope(user), hub=hub or None)
    return render(request, "blotter.html", trades=trades, hubs=trading.HUBS, selected_hub=hub)


@app.get("/positions")
def positions(request: Request, user: User = Depends(page_user)):
    trades = db.list_trades(trader=trade_scope(user))
    return render(request, "positions.html", positions=trading.compute_positions(trades, current_marks()))


# ---------------------------------------------------------------- JSON API


@app.get("/api/health")
def health():
    return {"status": "ok", "env": APP_ENV, "today": today().isoformat()}


@app.post("/api/login")
def api_login(request: Request, payload: dict = Body(...)):
    user = auth.authenticate(str(payload.get("username", "")), str(payload.get("password", "")))
    if user is None:
        return JSONResponse({"detail": "Invalid username or password"}, status_code=401)
    request.session["user"] = user.username
    return {"username": user.username, "display_name": user.display_name, "role": user.role}


@app.post("/api/logout")
def api_logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/prices")
def api_prices(_: User = Depends(api_user)):
    return {"as_of": today().isoformat(), "marks": current_marks()}


@app.get("/api/trades")
def api_trades(hub: str | None = None, user: User = Depends(api_user)):
    return {"trades": db.list_trades(trader=trade_scope(user), hub=hub)}


@app.post("/api/trades", status_code=201)
def api_create_trade(payload: dict = Body(...), user: User = Depends(api_user)):
    if not user.can_trade:
        return JSONResponse({"detail": "Your role cannot book trades"}, status_code=403)
    confirmed = bool(payload.get("confirm_price", False))
    trade, issues = book_trade(user, payload, confirmed)
    if issues:
        return JSONResponse({"errors": [i.as_dict() for i in issues]}, status_code=422)
    return trade


@app.get("/api/positions")
def api_positions(user: User = Depends(api_user)):
    trades = db.list_trades(trader=trade_scope(user))
    return trading.compute_positions(trades, current_marks())


@app.post("/api/test/reset")
def api_test_reset():
    """Wipe all trades. Only exists in the test environment, never in production."""
    if APP_ENV != "test":
        raise HTTPException(status_code=404)
    db.reset()
    return {"ok": True}
